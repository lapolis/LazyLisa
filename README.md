# LazyLisa

Auto Post on "all" social media everything published on Instagram, because she is not bothered to do it.

The following config file assume you created the session file for instaloader. If you didn't, you have two ways to do that:
- get it from your current browser -> https://raw.githubusercontent.com/instaloader/instaloader/master/docs/codesnippets/615_import_firefox_session.py
- from cmd line do `instaloader -l <username>` in order to create the file

SESSION FILES WORKS BETTER - Insta tend to block the login attempts after a while

File `API_KEYS.conf` layout example:
<br>
```
## Uncomment what you need and ad all the keys/tokens

[Instagram]
user = <username to login with>
target_profile = <profile to scrape>
 
## [Telegram]
## TOKEN = 
## CHATID = 
## 
## [Pinterest]
## SESSION = <_pinterest_sess cookie straight outta ya browser>
## BOARD = <name (in palintext) of the board you want to post to>
## 
## [Tumblr]
## ## https://api.tumblr.com/console/calls/user/info
## CONSUMERKEY = 
## CONSUMERSECRET = 
## OAUTHTOKEN = 
## OAUTHSECRET = 
## 
## [Twitter]
## APIKEY = 
## APIKEYSECRET = 
## ACCESSTOKEN = 
## ACCESSSECRET = 
## BEARERTOKEN = 
```
<br>
