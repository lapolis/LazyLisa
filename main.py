#!/usr/bin/env python3

import os
import time
import tweepy
import argparse
import filetype
import requests
import pytumblr
import threading
import configparser

from instaloader import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC

# import IPython; IPython.embed(); exit()

# import chromedriver_autoinstaller
# chromedriver_autoinstaller.install()

config = configparser.ConfigParser()
config.read( os.getcwd() + '/API_KEYS.conf' )

if 'Telegram' in config:
	telegram_token = config['Telegram']['TOKEN']
	telegram_chat_id = config['Telegram']['CHATID']
	telegram_user = config['Telegram']['USER']
else:
	telegram_token = ''
	telegram_chat_id = ''
	telegram_user = ''

status = 'start'

def send_msg(msg):
	if telegram_token and telegram_chat_id:
		method  = 'sendMessage'
		requests.post( url=f'https://api.telegram.org/bot{telegram_token}/{method}', data={'chat_id': telegram_chat_id, 'text': msg} ).json()

def check_telegram_msg(path):
	global status
	c = 0
	# n = time.time()
	# a = time.time()
	# diff = a - n

	while True:
		try:
			r = requests.get( url=f'https://api.telegram.org/bot{telegram_token}/getUpdates?offset=100' ).json()
			updates_arr = r['result']
			if len(updates_arr) > 0 :
				for u in updates_arr[::-1]:
					msg = u['message']['text']
					chat = u['message']['chat']['id']
					username = u['message']['chat']['username']
					date = u['message']['date']
					if username == telegram_user and str(chat) == telegram_chat_id:
						if msg != status:
							status = msg
						break
		except Exception as e:
			log = f'Telegram check broke -> {e}'
			if c > 15:
				logit(log,1)
				c = 0
			else:
				logit(log)

		time.sleep(1.5)

def logit(msg, send=0):
	print(f'{time.strftime("%Y/%m/%d-%H:%M:%S")} - {msg}')
	if send:
		send_msg(msg)

def insta_login(path, user, passwd):
	insta = instaloader.Instaloader(sanitize_paths=True,dirname_pattern=path)
	
	try:
		insta.load_session_from_file(user)
		return insta
	except Exception as e:
		logit(f'Session file for user {user} is not present.')

	try:
		if passwd:
			insta.login(user, passwd)
		else:
			insta.interactive_login(user)
	except Exception as e:
		msg = f'Insta broke at login -> {e}'
		logit(msg, 1)
		insta = False

	return insta

def get_latest_post(path, target_profile, insta, debug_post=False):
	## requesting a password
	# insta.interactive_login(user)
	try:
		profile = Profile.from_username(insta.context, target_profile)
	except Exception as e:
		msg = f'Insta getting profile broke -> {e}'
		logit(msg, 1)
		return False

	try:
		posts = profile.get_posts()
	except Exception as e:
		msg = f'Insta getting post broke -> {e}'
		logit(msg, 1)
		return False

	for p in posts:
		# print(p.title)
		# print(p.get_is_videos())
		# print(p.caption_hashtags)
		# print(p.caption)
		# print(p.is_video)
		# print(p.video_url)
		# print(p.shortcode)
		if p.is_pinned:
			logit(f'Skipping pinned {p.shortcode}')
			continue

		if debug_post and p.shortcode != debug_post:
			logit(f'Skipping post {p.shortcode}')
			continue

		latedt_post_path = os.path.join(path, 'latest.post')
		perm = 'r+' if os.path.isfile(latedt_post_path) else 'w+'
		with open(latedt_post_path, perm) as f:
			if p.shortcode == f.read().strip() and not debug_post:
				return False
			else:
				logit(f'Deleting and downloading {p.shortcode}')
				for file_name in os.listdir(path):
					file_path = os.path.join(path, file_name)
					if 'latest.post' not in file_path:
						os.remove(file_path)
				f.seek(0, 0)
				f.write(p.shortcode)

				with open(os.path.join(path, 'hashtags.tags'), 'w+') as file_tags:
					file_tags.write(' '.join(p.caption_hashtags))
				with open(os.path.join(path, 'post.caption'), 'w+') as file_caption:
					for par in p.caption.split('\n\n'):
						file_caption.write('\n'.join(filter(lambda x:x[0]!='#' and x[0]!='.', par.split('\n'))) + '\n\n')

				try:
					post_down_bool = insta.download_post(p, target=profile)
				except Exception as e:
					msg = f'Insta downloading post failed -> {e}'
					logit(msg, 1)
					post_down_bool = False

				return post_down_bool

def file_check(path):
	logit('Checking file types')
	post_content = {}
	for file_name in os.listdir(path):
		file_path = os.path.join(path, file_name)

		if file_name.endswith('.txt'):
			post_content[file_path] = 'plain/text'
		elif file_name.endswith('.tags'):
			post_content[file_path] = 'plain/hashtags'
		elif file_name.endswith('.caption'):
			post_content[file_path] = 'plain/caption'
		elif file_name.endswith('.post'):
			post_content[file_path] = 'plain/code'
		else:
			type_obj = filetype.guess(file_path)
			if type_obj is None:
				post_content[file_path] = 'fuffa'
			else:
				post_content[file_path] = type_obj.mime

	return post_content

def split_text(file, max_chars):
	## 99% from https://github.com/abzicht/sweet
	## cheers abzicht

	thread = ''
	with open(file, 'r') as fr:
		# post_text_lines = fr.readlines()
		for l in fr.readlines():
			# if l.strip() != '.' and l != '\n':
			if l.strip() != '.':
				thread += l

	if len(thread) <= max_chars:
		return [thread]

	thread_ = ''
	max_chars -= 4
	for line in thread.split('\n\n'):
		# line = line.replace('\n', ' ')
		line = line.replace('  ', ' ')
		thread_ += line + '\n\n'
	thread = thread_

	separators = ['\n\n', '.', ' ']
	if len(thread) <= max_chars:
		return [thread]

	post_text = []
	sep_index = 0
	while len(thread) > 0:
		thread_index = max_chars
		while thread_index > 0 and len(thread) > max_chars:
			if thread[thread_index] == separators[sep_index]:
				post_text += [thread[0:thread_index+1].strip()]
				thread = thread[thread_index+1:]
				thread_index = max_chars
				sep_index = 0
			thread_index -= 1
		if sep_index + 1 >= len(separators):
				post_text += [thread[0:max_chars+1].strip()]
				thread = thread[max_chars+1:]
				sep_index = 0
		else:
			sep_index = min(sep_index + 1, len(separators)-1)

	for i in range(len(post_text)):
		post_text[i] = post_text[i] + f' ({i+1}/{len(post_text)})'

	return post_text

def tweet_it(post_content, api_key, api_secret, access_token, access_token_secret):
	auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token=access_token, access_token_secret=access_token_secret)
	api = tweepy.API(auth, timeout=120, retry_count=3, retry_delay=30, retry_errors=[400,404,429,500])

	## up to 4 photos or 1 animated GIF or 1 video in a Tweet.
	## assuming the account owner either posts a carousel or a single video
	if 'video/mp4' in post_content.values():
		media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4']
		async_finalize = True
		media_category = 'amplify_video'
	else:
		media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']
		async_finalize = False
		media_category = 'tweet_image'

	txt_file_path = [k for k, v in post_content.items() if v == 'plain/text'][0]
	## 280 characters max!! for Insta!
	post_arr = split_text(txt_file_path, 260)

	# Tweet a video
	media_arr = []
	if len(media_to_upload) > 4:
		media_to_upload = media_to_upload[:4]

	for file_path in media_to_upload:
		# https://developer.twitter.com/en/docs/twitter-api/v1/data-dictionary/object-model/entities#media
		media_arr.append(api.chunked_upload(file_path.split('/')[-1], file=open(file_path, 'rb'), file_type=post_content[file_path], wait_for_async_finalize=async_finalize, media_category=media_category))
	media_ids = [i.media_id_string for i in media_arr]

	try:
		ret = api.update_status(status=post_arr[0], media_ids=media_ids, possibly_sensitive=False, lat=+51.50, long=-0.11, display_coordinates=False)
	except Exception as e:
		err = f'Twitter failed with error: {e}'
		logit(err, 1)
		return 1

	time.sleep(5)
	tweetid = ret.id
	screen_name = ret.user.screen_name
	if len(post_arr) != 1:
		for status in post_arr[1:]:
			tweetid = api.update_status(status=status, in_reply_to_status_id=tweetid).id
			time.sleep(5)

	msg = f'New tweet is up -> https://twitter.com/{screen_name}/status/{ret.id}'
	logit(msg, 1)

def tumblr_post_it(post_content, consumer_key, consumer_secret, oauth_token, oauth_secret):
	client = pytumblr.TumblrRestClient(consumer_key, consumer_secret, oauth_token, oauth_secret)
	account_name = client.info()['user']['name']

	hashtags_file_path = [k for k, v in post_content.items() if v == 'plain/hashtags'][0]
	caption_file_path = [k for k, v in post_content.items() if v == 'plain/caption'][0]

	with open(hashtags_file_path, 'r') as fr:
		tags = fr.read().split(' ')

	# assuming that it is always only one block (using the function just to clean that up)
	caption = split_text(caption_file_path, 4000)[0]

	if 'video/mp4' in post_content.values():
		media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4'][0]
		client.create_video(account_name, state='published', tags=tags, format='markdown', data=media_to_upload, caption=caption)
	else:
		media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']
		client.create_photo(account_name, state='published', tags=tags, format='markdown', data=media_to_upload, caption=caption)

	time.sleep(10)

	post_id = client.posts(account_name)['posts'][0]['id']
	msg = f'Tumblr post done -> https://www.tumblr.com/{account_name}/{post_id}'
	logit(msg, 1)

def pin_it(post_content, email, password, board_name, target_profile, headless, debug_pinterest=False):
	# post_content, pin_APP_ID, pin_APP_SECRET, pin_BOARD_ID, pin_APP_TOKEN, pin_REDIRECT, pin_INTERESTS
	# 500 chars limit
	# 5 files limit
	
	hashtags_file_path = [k for k, v in post_content.items() if v == 'plain/hashtags'][0]
	caption_file_path = [k for k, v in post_content.items() if v == 'plain/caption'][0]
	code_file_path = [k for k, v in post_content.items() if v == 'plain/code'][0]

	with open(hashtags_file_path, 'r') as fr:
		# tags_arr = fr.read().split(' ')
		tags = fr.read()

	with open(code_file_path, 'r') as fr:
		code = fr.read().strip()
	insta_post_url = f'https://www.instagram.com/p/{code}'


	# if 'video/mp4' in post_content.values():
	# 	media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4']
	# else:
	# 	media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']
	
	vids = [k for k, v in post_content.items() if v == 'video/mp4']
	media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']
	
	# They can read the remaining test in insta
	if vids:
		post_header = f'Full video on Insta!\n\n'
	else:
		post_header = f'Full post on Insta!\n\n'
	caption = split_text(caption_file_path, 480 - len(post_header))[0]
	caption = f"{post_header}{caption.replace(' (1/2)', '')}"

	if len(media_to_upload) > 4:
		media_to_upload = media_to_upload[:4]

	chrome_options = Options()
	if headless:
		chrome_options.add_argument("--headless")

	chrome_options.add_argument("--window-size=1920,1080")

	chrome_options.add_argument("--disable-blink-features")
	chrome_options.add_argument("--disable-blink-features=AutomationControlled")
	chrome_options.add_experimental_option("excludeSwitches", ["enable-automation","dom-automation","enable-experimental-ui-automation","auto-open-devtools-for-tabs"])
	chrome_options.add_experimental_option('useAutomationExtension', False)

	# install chrome bin
	# driver = webdriver.Chrome(ChromeDriverManager().install(),options=chrome_options)

	driver = webdriver.Chrome(options=chrome_options)

	# change UA
	driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36'})
	driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

	driver.implicitly_wait(30)

	pinterest_home = 'https://www.pinterest.com/'
	pinterest_profile = f'https://www.pinterest.co.uk/{board_name}/'
	# home_wait = '//a[starts-with(@href, "https://analytics.pinterest.com")]'
	profile_wait = f'//*[contains(text(), "{board_name}")]'
	profile_click = f'//a[@href="/{board_name}/"]'

	# create_dropdown = '//div[contains(text(), "Create")]'
	# create_pin_dropdown = '//div[contains(text(), "Create Pin")]'
	# create_dropdown = "//div[text()='Create']"
	# create_pin_dropdown = "//div[text()='Create Pin']"

	pin_builder = 'https://www.pinterest.com/pin-builder/'
	drop_down_menu = '//button[@data-test-id="board-dropdown-select-button"]'
	board_lp = f'//div[@title="{board_name}"]'
	title = '//textarea[contains(@placeholder, "title")]'
	description = '//div[starts-with(@class, "public-DraftStyleDefault")]'
	destination_link = '//textarea[contains(@placeholder, "destination")]'
	# tags_path = '//input[contains(@placeholder, "tags")]'
	upload_media = '//input[@aria-label="File upload"]'
	alt_text = '//div[contains(text(), "Add alt text")]'
	alt_text_write = '//textarea[@placeholder="Explain what people can see in the Pin"]'
	publish = '//div[contains(text(), "Publish")]'
	post_done_message = '//h1[contains(text(), "You created a Pin!")]'
	link_to_pin = '//div[@data-test-id="seeItNow"]/a'
	link_to_pin_bckw = '//div[contains(text(), "See your Pin")]/../../../..//a'

	# might need to enter the popup first
	# popup = '//div[@name="trap-focus"]'
	# case insensitive regex (i)
	# popup_exit_click = '//button[matches(@aria-label, "close", "i")][@type="button"]'
	# this might work too, need to test
	# popup_exit_click = '//button[contains(lower-case(@aria-label), "close")]'
	popup_exit_click = '//button[contains(@aria-label, "lose") and @type="button"]'

	## Login!!
	# driver.get(pinterest_home)
	# time.sleep(5)
	# driver.add_cookie({"name": "_pinterest_sess", "value": _pinterest_sess, "sameSite": "None", "HttpOnly": "true", "Secure": "true"})

	driver.get("https://pinterest.com/login")
	try:
		WebDriverWait(driver, 35).until( EC.element_to_be_clickable((By.ID, "email")) )
		driver.find_element(By.ID, "email").send_keys(email)
		driver.find_element(By.ID, "password").send_keys(password)
		logins = driver.find_elements(By.XPATH, "//*[contains(text(), 'Log in')]")
		for login in logins:
			login.click()
		WebDriverWait(driver, 35).until( EC.invisibility_of_element((By.ID, "email")) )
		msg = f'Successfully logged in with account {email}'
		logit(msg)
		driver.get("https://pinterest.com/")
		time.sleep(6)
	except Exception as e:
		msg = f'Failed to login {e}'
		logit(msg, 1)
		driver.close()
		return False

	try:
		driver.find_element('xpath', popup_exit_click).click()
	except Exception as e:
		msg = f'No pop-up to click -> {e}'
		logit(msg)

	try:
		# driver.get(pinterest_profile)
		_ = WebDriverWait(driver, 35 ).until(EC.presence_of_element_located((By.XPATH, profile_click)))
		driver.find_element('xpath', profile_click).click()
		time.sleep(6)
		driver.find_element('xpath', profile_click).click()
		time.sleep(4)
	except Exception as e:
		msg = f'Failed to click Profile -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		_ = WebDriverWait(driver, 35 ).until(EC.presence_of_element_located((By.XPATH, profile_wait)))
		driver.get(pin_builder)
	except Exception as e:
		msg = f'Pinterest failed at login -> {e}\nLooking for XPATH -> {profile_wait}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	time.sleep(8)
	try:
		_ = WebDriverWait(driver, 35 ).until(EC.presence_of_element_located((By.XPATH, drop_down_menu)))
		_ = WebDriverWait(driver, 35 ).until(EC.presence_of_element_located((By.XPATH, title)))
	except Exception as e:
		msg = f'Pinterest failed New Pin menu -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', drop_down_menu).click()
	except Exception as e:
		msg = f'Pinterest failed finding DropDown menu -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', board_lp).click()
	except Exception as e:
		msg = f'Pinterest failed fidning board -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', title).send_keys(f'Insta (@lisa.lunaticpin) for full post <3')
	except Exception as e:
		msg = f'Pinterest failed adding the title -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		description_elem = driver.find_element('xpath', description)
		# To keep emoji and stuff
		driver.execute_script(
		f'''
		const text = `{caption}`;
		const dataTransfer = new DataTransfer();
		dataTransfer.setData('text', text);
		const event = new ClipboardEvent('paste', {{
		clipboardData: dataTransfer,
		bubbles: true
		}});
		arguments[0].dispatchEvent(event)
		''',
		description_elem)
	except Exception as e:
		msg = f'Pinterest failed JS fuckery -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', destination_link).send_keys(insta_post_url)
	except Exception as e:
		msg = f'Pinterest failed to set destination -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', upload_media).send_keys(media_to_upload[0])
	except Exception as e:
		msg = f'Pinterest failed to upload media -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', alt_text).click()
	except Exception as e:
		msg = f'Pinterest failed to click alt_text -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		driver.find_element('xpath', alt_text_write).send_keys(f'Latest post from my Instagram. Go check it out on my {target_profile} page!')
	except Exception as e:
		msg = f'Pinterest failed to write alt_text -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False

	try:
		# driver.find_element('xpath', tags_path).send_keys(tags)
		driver.find_element('xpath', publish).click()
	except Exception as e:
		msg = f'Pinterest failed to click publish -> {e}'
		logit(msg, 1)
		if debug_pinterest:
			with open(f'/tmp/debug_pin_{time.strftime("%Y-%m-%d_%H:%M:%S")}.html','w+') as fw:
				fw.write(driver.page_source)
		driver.close()
		return False		


	# just give it a bit of extra time
	_ = WebDriverWait(driver, 120 ).until(EC.presence_of_element_located((By.XPATH, post_done_message)))
	pin_url = driver.find_element('xpath', link_to_pin).get_attribute('href')

	driver.close()

	msg = f'Pinterest pin done -> {pin_url}'
	logit(msg, 1)

	return True

def wait_start(runTime):
	while time.strftime('%H:%M') != runTime:
		time.sleep(1)

def main():
	p = argparse.ArgumentParser(description='Hi LazyLisa!')
	p.add_argument('-ntw', '--no_twitter', action='store_true', default=False, help='Do not post on Twitter.')
	p.add_argument('-npi', '--no_pinterest', action='store_true', default=False, help='Do not post on Pinterest.')
	p.add_argument('-dpi', '--debug_pinterest', action='store_true', default=False, help='Write HTML page content in /tmp on failure.')
	p.add_argument('-ntu', '--no_tumblr', action='store_true', default=False, help='Do not post on Tumblr.')
	p.add_argument('-nin', '--no_insta_check', action='store_true', default=False, help='Mark the downloaded post as the last one.')
	p.add_argument('-nh', '--no_headless', action='store_false', default=True, help='Show the Selenium browser.')
	p.add_argument('-dp', '--debug_post', default=False, help='Download specific Instagram post using unique shortcode.')
	p.add_argument('-s', '--sleep', default=None, help='Sleep time in seconds between checks (default 30 min).')
	p.add_argument('-or', '--one_round', default=False, action='store_true', help='Do only one loop and exit.')
	args = p.parse_args()

	time_sleep = int(args.sleep) if args.sleep else 0
	one_round = args.one_round

	post_fold = os.path.join(os.getcwd(),'posts')
	if not os.path.isdir(post_fold):
		os.mkdir(post_fold)

	if 'Instagram' in config:
		INSTA_USER = config['Instagram']['user']
		if 'pass' in config['Instagram']:
			INSTA_PASS = config['Instagram']['pass']
		else:
			INSTA_PASS = ''
		target_profile = config['Instagram']['target_profile']
	else:
		logit('EXITING LazyLisa - (missing insta creds)')
		exit(1)

	tweet = False
	pin = False
	tumblr = False

	if 'Twitter' in config and not args.no_twitter:
		try:
			twitter_API = config['Twitter']['APIKEY']
			twitter_API_SECRET = config['Twitter']['APIKEYSECRET']
			twitter_TOKEN = config['Twitter']['ACCESSTOKEN']
			twitter_TOKEN_SECRET = config['Twitter']['ACCESSSECRET']
			tweet = True
		except Exception as e:
			logit(f'Twitter config is broken with error: {e}')

	if 'Tumblr' in config and not args.no_tumblr:
		try:
			tumblr_CUSTOMER_KEY = config['Tumblr']['CONSUMERKEY']
			tumblr_CUSTOMER_SECRET = config['Tumblr']['CONSUMERSECRET']
			tumblr_OAUTH_TOKEN = config['Tumblr']['OAUTHTOKEN']
			tumblr_OAUTH_SECRET = config['Tumblr']['OAUTHSECRET']
			tumblr = True
		except Exception as e:
			logit(f'Tumblr config is broken with error: {e}')

	if 'Pinterest' in config and not args.no_pinterest:
		try:
			pinterest_EMAIL = config['Pinterest']['PINEMAIL']
			pinterest_PASSWD = config['Pinterest']['PINPASSWD']
			pinterest_BOARD = config['Pinterest']['BOARD']
			pin = True
		except Exception as e:
			logit(f'Pinterest config is broken with error: {e}')

	insta = insta_login(post_fold, INSTA_USER, INSTA_PASS)
	if not insta:
		logit('EXITING LazyLisa - (not able to login)')
		exit(1)

	# Starting Telegram checker
	if 	telegram_token and telegram_chat_id and telegram_user:
		thread = threading.Thread(target=check_telegram_msg, args=(post_fold,))
		thread.daemon = True
		thread.start()

	msg = f'LazyLisa started!\nTumblr: {tumblr}\nTwitter: {tweet}\nPinterest: {pin}'
	send_msg(msg)

	while True:

		if status == 'stop':
			msg = 'EXITING LazyLisa - (user requested)'
			logit(msg, 1)
			exit()
		elif status == 'pause':
			msg = 'LazyLisa paused!'
			logit(msg, 1)
			# time.sleep(time_sleep)
			continue
		elif status != 'start':
			msg = f'LazyLisa weird status -> {status}'
			logit(msg, 1)
			# time.sleep(time_sleep)
			continue

		if args.no_insta_check:
			new_post = True
		else:
			try:
				new_post = get_latest_post(post_fold, target_profile, insta, args.debug_post)
			except Exception as e:
				msg = f'Something broke down with Instagram -> {e}'
				logit(msg, 1)
				new_post = False
		
		if new_post:
			logit('Got latest post, posting soon.', 1)
			post_content = file_check(post_fold)

			if tweet:
				logit('Tweeting now!')
				try:
					tweet_it(post_content, twitter_API, twitter_API_SECRET, twitter_TOKEN, twitter_TOKEN_SECRET)
				except Exception as e:
					msg = f'Not able to Tweet -> {e}'
					logit(msg, 1)
			if pin:
				logit('Posting on Pinterest')
				attempt = 0
				while attempt < 6:
					try:
						done = pin_it(post_content, pinterest_EMAIL, pinterest_PASSWD, pinterest_BOARD, target_profile, args.no_headless, args.debug_pinterest)
						attempt = 666 if done else attempt+1
					except Exception as e:
						msg = f'Not able to Pin it - (attempt {attempt}) -> {e}'
						logit(msg, 1)
						attempt += 1
			if tumblr:
				logit('Posting on Tumblr')
				try:
					tumblr_post_it(post_content, tumblr_CUSTOMER_KEY, tumblr_CUSTOMER_SECRET, tumblr_OAUTH_TOKEN, tumblr_OAUTH_SECRET)
				except Exception as e:
					msg = f'Not able to Tumblr it -> {e}'
					logit(msg, 1)

		else:
			logit('Nothing to do now')

		if one_round:
			exit()
		elif time_sleep:
			time.sleep(time_sleep)
		else:
			time_to_wait = '19:00'
			logit(f'Waiting {time_to_wait}')
			wait_start(time_to_wait)

if __name__ == '__main__' :
	main()
