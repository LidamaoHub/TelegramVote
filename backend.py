import telebot,time
from flask import Flask, request,jsonify
from telebot.types import ReplyKeyboardMarkup,User
from telebot.util import quick_markup
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import random
import string
import urllib.parse
from web3 import Web3
from eth_account.messages import encode_defunct

client = pymongo.MongoClient("mongodb://localhost/", 27017)

user_db = client.tgvote.users
vote_db = client.tgvote.votes


TOKEN =  os.getenv('TOKEN')
RPC_URL = "https://mainnet.infura.io/v3/d10c4ff706c546c485a8d9d92d1e5096"
abi = [{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
bot = telebot.TeleBot(TOKEN, threaded=False)
user_name_list = ['投票选项1','投票选择2','投票选择3']

vote_msg = "请对每一个候选人进行投票(当前结果仅你能看到),点击提案相关按钮可以切换你的态度,点击一次同意,再次点击不同意,再点一次弃权"

app = Flask(__name__)

w3 = Web3(Web3.HTTPProvider(RPC_URL))  #
contract_address = w3.toChecksumAddress('0xbd7abbee471f7a0ffe5fcc4ce176d92ca3f4dffe')

contract = w3.eth.contract(address=contract_address, abi=abi)


# 你的 Webhook 地址 (例如: https://yourdomain.com/<token>/)
# 这里需要一个公网地址,用于接受tg的回调部分,我个人不建议用token作为回调,容易被抓包攻击
WEBHOOK_URL = f"https://vote.lidamao.tech/bbb"

# # 处理消息的装饰器
# @bot.message_handler(func=lambda message: True)
# def echo_message(message):
#     print(message)
#     bot.send_message(message.chat.id, f"收到: {message.text}")


chat_length = 3

def random_message(length=10):
    """生成随机文本"""
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))


@bot.message_handler(commands=['start']) 
def get_data(message):
    markup = ReplyKeyboardMarkup(resize_keyboard = True)
    markup.add('/vote','/regist')
    msg = bot.send_message(message.chat.id, "欢迎使用SecretVote机器人程序,本程序用于隐私下投票\n第一次使用前请先回复或点击下方的 \\regist 命令来绑定钱包,只有持有lxdao builder card的用户可以投票", reply_markup = markup)

@bot.message_handler(commands=['ping'])
def test(message):
    print(message.chat)
    bot.send_message(message.chat.id, "pong")
   
@bot.message_handler(commands=['vote'])
def vote(message):
    print(message.chat)
    
    user_id = message.chat.id 
    btns = get_vote_list(user_id)
    

    bot.send_message(message.chat.id, vote_msg, reply_markup = quick_markup(btns, row_width = 1))

 
@bot.message_handler(commands=['regist'])
def regist(message):
    user_id = message.chat.id 
    user_info = user_db.find_one({'id':user_id})
    message_to_sign = f"{random_message()}_{user_id}"
    

    callback_url = "https://vote.lidamao.tech/verify"
    verification_url = f"https://verify.lidamao.tech/?message={message_to_sign}&callback={urllib.parse.quote(callback_url)}"

    if user_info and user_info.get('address'):
        user_db.update_one({'id':user_id},{"$set":{"message":message_to_sign}})
        bot.send_message(message.chat.id, f"你已经注册,钱包地址为:{user_info['address']}\n如果想要修改,请点击以下地址:\n{verification_url}")
    else:
        
        if user_info:
            user_db.update_one({'id':user_id},{"$set":{"message":message_to_sign}})
        else:
            user_db.insert_one({'id':user_id,"message":message_to_sign,"state":'pending'})
        


        bot.send_message(message.chat.id, f"请点击以下网址绑定和验证你的地址:\n{verification_url}")


def get_vote_list(user_id):
    vote_list = vote_db.find({'user_id':user_id,'name':{'$in':user_name_list}})
    vote_dic ={}
    btns = {}

    for x in vote_list:
        vote_dic[x['name']] = x['side']
    print("!!",vote_dic)

    for name in user_name_list:
        new_side = vote_dic.get(name,0)

        l = ['请点击选择',"赞同✅",'反对🙅🏻‍♀️'][new_side]
        name_ = f"{name}[{l}]"
        btns[name_] = {"callback_data": f"vote_{name}"}
    
    return btns


@bot.callback_query_handler(func=lambda call: True)
def refresh(call):
    if call.data.startswith("vote_"):

        name = call.data.replace("vote_","")
        user_id = call.from_user.id 
        user_info = user_db.find_one({"id":user_id})
        if not user_info or not user_info.get("address"):
            bot.send_message(call.message.chat.id, f"请回复 \\regist 绑定auth后操作")
            return
        
        user_side = vote_db.find_one({'user_id':user_id,"name":name})
        if user_side:
            side = user_side['side']
            side = (side+1)%3
        else:
            side = 1 

        vote_db.update_one({'user_id':user_id,"name":name},{"$set":{'side':side}},upsert=True)
        # 获取新的内容
        btns = get_vote_list(user_id)



        bot.edit_message_text(chat_id=call.message.chat.id,message_id=call.message.id,text= vote_msg, reply_markup = quick_markup(btns, row_width = 1))
        try:
            bot.answer_callback_query(call.id)
        except Exception as e:
            print(f"报错{e}")
        
    

@app.route("/bbb",methods=["GET","POST"])
def router_name():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)



@app.route('/verify', methods=['POST'])
def verify_signature():
    data = request.json
    message = data.get('message')
    user = user_db.find_one({'message':message})
    if not user:
        return jsonify({'error': "错误的请求"}), 500
    address = data.get('address')
    signature = data.get('signature')
    # 验证签名
    if not all([message, address, signature]):
        return jsonify({'error': '缺少必要的参数'}), 400

    try:
        w3 = Web3()
        message = encode_defunct(text=message)
        signer_address = w3.eth.account.recover_message(message, signature=signature)
        signer_address = signer_address.lower()
        addr = w3.toChecksumAddress(signer_address)
        balance = contract.functions.balanceOf(addr).call()

        if balance>0:
            user_db.update_one({'id':user['id']},{"$set":{"state":"verified","address":signer_address}})
            
            bot.send_message(user['id'], f"你已成功绑定地址:{addr}")
            return jsonify({'success': True, 'message': '签名验证成功'})
        else:
            bot.send_message(user['id'], f"地址内资产数量不足")
            return jsonify({'success': True, 'message': '签名验证成功,但是地址不在权限列表中'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    # 设置 Webhook
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    # 启动 Flask 服务器
    app.run(host="127.0.0.1", port=4338, debug=True)
