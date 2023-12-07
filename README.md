# TelegramVote

TelegramVote is a project for tgbot test

It's very simple, you can even deploy it on vercel serverless( but not now)

If you want to run your own vote, just deploy a static project on cloudflare or vercel with the index.html and get the url

then change the verify page url in `backend.py`

#### deploy backend

before you run backend.py, make sure the mongo service is deployed

> Recommended Atlas services for mongodb storage, and change mongo uri in the top of the backend.py

you should write a `.env` file and set your token like this 

```
TOKEN='xxx:xxxx'
```

you can get this token from the @botfather in tg


then just run `python3 backend.py` 
