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
## APPID = 
## APPSECRET = 
## REFRESHTOKEN = 
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

Use the following to extract Pinterest cookies.

```py
from glob import glob
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect

try:
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")


def get_cookiefile():
    default_cookiefile = {
        "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
        "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
    }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")
    cookiefiles = glob(expanduser(default_cookiefile))
    if not cookiefiles:
        raise SystemExit("No Firefox cookies.sqlite file found. Use -c COOKIEFILE.")
    return cookiefiles[0]


def import_session(cookiefile, sessionfile):
    print("Using cookies from {}.".format(cookiefile))
    conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
    try:
        cookie_data = conn.execute(
            "SELECT name, value FROM moz_cookies WHERE baseDomain='pinterest.co.uk'"
        )
    except OperationalError:
        cookie_data = conn.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE '%pinterest.co.uk'"
        )
    with open('/tmp/pin_cookies', 'w+') as cw:
        for cc in cookie_data.fetchall():
            cw.write(f'{cc[0]} = {cc[1]}\n')

if __name__ == "__main__":
    try:
        import_session(args.cookiefile or get_cookiefile(), args.sessionfile)
    except (ConnectionException, OperationalError) as e:
        raise SystemExit("Cookie import failed: {}".format(e))
```