# LazyLisa

Auto Post everything she publishes on Instagram because she is not bothered to do it.

File `API_KEYS.conf` layout example:
<br>
```
## Uncomment what you need and ad all the keys/tokens

[Instagram]
user = <username to login with>
# if password not included will be asked
pass = <password for that user>
target_profile = <profile to scrape>
# The script upon login will give priority to session files
# utility to get the session file from firefox -> https://raw.githubusercontent.com/instaloader/instaloader/master/docs/codesnippets/615_import_firefox_session.py
# otherwise, from cmd line do `instaloader -l <username>` in order to create the file
# SESSION FILES WORKS BETTER - Insta tend to block the login attempts after a while
 
## [Telegram]
## TOKEN = 
## CHATID = 
## 
## [Pinterest]
## # This is your _pinterest_sess cookie straight outta ya browser
## SESSION = 
## # This is the name (in palintext) of the board you want to post to
## BOARD = 
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
