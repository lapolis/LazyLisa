#!/usr/bin/env python3

import os
import time
import tweepy
import filetype
import requests
import pytumblr
import configparser
from instaloader import *

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# import IPython; IPython.embed(); exit()

# import chromedriver_autoinstaller
# chromedriver_autoinstaller.install()

config = configparser.ConfigParser()
config.read( os.getcwd() + '/API_KEYS.conf' )
if 'Telegram' in config:
	telegram_token = config['Telegram']['TOKEN']
	telegram_chat_id = config['Telegram']['CHATID']
else:
	telegram_token = ''
	telegram_chat_id = ''

def send_msg(msg):
	if telegram_token and telegram_chat_id:
		method  = 'sendMessage'
		requests.post( url=f'https://api.telegram.org/bot{telegram_token}/{method}', data={'chat_id': telegram_chat_id, 'text': msg} ).json()

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

def get_latest_post(path, target_profile, insta):
	## requesting a password
	# insta.interactive_login(user)
	try:
		profile = Profile.from_username(insta.context, target_profile)
	except Exception as e:
		msg = f'Insta getting profile broke -> {e}'
		logit(msg, 1)

	try:
		posts = profile.get_posts()
	except Exception as e:
		msg = f'Insta getting post broke -> {e}'
		logit(msg, 1)

	for p in posts:
		# print(p.title)
		# print(p.get_is_videos())
		# print(p.caption_hashtags)
		# print(p.caption)
		# print(p.is_video)
		# print(p.video_url)

		# print(p.shortcode)
		latedt_post_path = os.path.join(path, 'latest.post')
		perm = 'r+' if os.path.isfile(latedt_post_path) else 'w+'
		with open(latedt_post_path, perm) as f:
			if p.shortcode == f.read().strip():
				return False
			else:
				logit('Deleting and downloading')
				for file_name in os.listdir(path):
					file_path = os.path.join(path, file_name)
					if 'latest.post' not in file_path:
						os.remove(file_path)
				f.seek(0, 0)
				f.write(p.shortcode)

				with open(os.path.join(path, 'hashtags.tags'), 'w+') as file_tags:
					file_tags.write(' '.join(p.caption_hashtags))
				with open(os.path.join(path, 'post.caption'), 'w+') as file_caption:
					file_caption.write('\n\n'.join(filter(lambda x:x[0]!='#', p.caption.split('\n\n'))))

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
	api = tweepy.API(auth)

	## up to 4 photos or 1 animated GIF or 1 video in a Tweet.
	## assuming the account owner either posts a carousel or a single video
	if 'video/mp4' in post_content.values():
		media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4']
	else:
		media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']

	txt_file_path = [k for k, v in post_content.items() if v == 'plain/text'][0]
	## 280 characters max!! for Insta!
	post_arr = split_text(txt_file_path, 275)

	# Tweet a video
	media_arr = []
	if len(media_to_upload) > 4:
		media_to_upload = media_to_upload[:4]

	for file_path in media_to_upload:
		# https://developer.twitter.com/en/docs/twitter-api/v1/data-dictionary/object-model/entities#media
		media_arr.append(api.chunked_upload(file_path.split('/')[-1], file=open(file_path, 'rb'), file_type=post_content[file_path], wait_for_async_finalize=True))
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

def pin_it(post_content, _pinterest_sess, board_name, target_profile):
	# post_content, pin_APP_ID, pin_APP_SECRET, pin_BOARD_ID, pin_APP_TOKEN, pin_REDIRECT, pin_INTERESTS
	# 500 chars limit
	# 5 files limit
	
	hashtags_file_path = [k for k, v in post_content.items() if v == 'plain/hashtags'][0]
	caption_file_path = [k for k, v in post_content.items() if v == 'plain/caption'][0]
	code_file_path = [k for k, v in post_content.items() if v == 'plain/code'][0]

	with open(hashtags_file_path, 'r') as fr:
		tags = fr.read().split(' ')

	with open(code_file_path, 'r') as fr:
		code = fr.read().strip()
	insta_post_url = f'https://www.instagram.com/p/{code}'

	# They can read the remaining test in insta
	post_ending = f'\n\nCheck the full post on Insta!'
	caption = split_text(caption_file_path, 499 - len(post_ending))[0]
	caption = caption.replace(' (1/2)', post_ending)

	if 'video/mp4' in post_content.values():
		media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4']
	else:
		media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']

	if len(media_to_upload) > 4:
		media_to_upload = media_to_upload[:4]

	chrome_options = Options()
	chrome_options.add_argument("--headless")
	chrome_options.add_argument("--window-size=1920,1080")
	driver = webdriver.Chrome(options=chrome_options)
	driver.implicitly_wait(15)

	pinterest_home = "https://www.pinterest.com/"
	pin_builder = "https://www.pinterest.com/pin-builder/"
	drop_down_menu = '//button[@data-test-id="board-dropdown-select-button"]'
	board_lp = f'//div[@title="{board_name}"]'
	title = '//textarea[@placeholder="Pin title"]'
	description = '//div[starts-with(@class, "public-DraftStyleDefault")]'
	destination_link = '//textarea[@placeholder="www.website.com"]'
	upload_media = '//input[@aria-label="File upload"]'
	alt_text = '//div[contains(text(), "Add alt text")]'
	alt_text_write = '//textarea[@placeholder="Explain what people can see in the Pin"]'
	publish = '//div[contains(text(), "Publish")]'
	post_done_message = '//h1[contains(text(), "You created a Pin!")]'
	link_to_pin = '//div[@data-test-id="seeItNow"]/a'
	link_to_pin_bckw = '//div[contains(text(), "See your Pin")]/../../../..//a'

	driver.get(pinterest_home)
	driver.add_cookie({"name": "_pinterest_sess", "value": _pinterest_sess, "sameSite": "None", "HttpOnly": "true", "Secure": "true"})
	driver.get(pin_builder)

	# wait and select the board to publish to
	_ = WebDriverWait(driver, 20 ).until(EC.presence_of_element_located((By.XPATH, drop_down_menu)))
	driver.find_element('xpath', drop_down_menu).click()
	driver.find_element('xpath', board_lp).click()
	driver.find_element('xpath', title).send_keys(f'Got a new post waiting for you on my Insta!')

	description_elem = driver.find_element('xpath', description)
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

	driver.find_element('xpath', destination_link).send_keys(insta_post_url)
	driver.find_element('xpath', upload_media).send_keys(media_to_upload[0])
	driver.find_element('xpath', alt_text).click()
	driver.find_element('xpath', alt_text_write).send_keys(f'Latest picture from my Instagram. Go check it out on my {target_profile} page!')
	driver.find_element('xpath', publish).click()

	# just give it a bit of extra time
	_ = WebDriverWait(driver, 60 ).until(EC.presence_of_element_located((By.XPATH, post_done_message)))
	pin_url = driver.find_element('xpath', link_to_pin).get_attribute('href')

	driver.close()

	msg = f'Pinterest pin done -> {pin_url}'
	logit(msg, 1)

def main():
	# os.system('clear')
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
		logit('XX Missing Insta creds')
		exit(1)

	tweet = False
	pin = False
	tumblr = False
	if 'Twitter' in config:
		try:
			twitter_API = config['Twitter']['APIKEY']
			twitter_API_SECRET = config['Twitter']['APIKEYSECRET']
			twitter_TOKEN = config['Twitter']['ACCESSTOKEN']
			twitter_TOKEN_SECRET = config['Twitter']['ACCESSSECRET']
			tweet = True
		except Exception as e:
			logit(f'Twitter config is broken with error: {e}')

	if 'Tumblr' in config:
		try:
			tumblr_CUSTOMER_KEY = config['Tumblr']['CONSUMERKEY']
			tumblr_CUSTOMER_SECRET = config['Tumblr']['CONSUMERSECRET']
			tumblr_OAUTH_TOKEN = config['Tumblr']['OAUTHTOKEN']
			tumblr_OAUTH_SECRET = config['Tumblr']['OAUTHSECRET']
			tumblr = True
		except Exception as e:
			logit(f'Tumblr config is broken with error: {e}')

	if 'Pinterest' in config:
		try:
			pinterest_SESSION = config['Pinterest']['SESSION']
			pinterest_BOARD = config['Pinterest']['BOARD']
			pin = True
		except Exception as e:
			logit(f'Pinterest config is broken with error: {e}')

	insta = insta_login(post_fold, INSTA_USER, INSTA_PASS)
	if not insta:
		exit(1)

	msg = f'LazyLisa started!\nTumblr: {tumblr}\nTwitter: {tweet}\nPinterest: {pin}'
	send_msg(msg)

	while True:
		try:
			new_post = get_latest_post(post_fold, target_profile, insta)
		except Exception as e:
			msg = f'Something broke down with Instagram -> {e}'
			logit(msg, 1)
			new_post = False
		
		# if True:
		# 	logit('NOT - DEBUG - Got latest post')

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
				try:
					pin_it(post_content, pinterest_SESSION, pinterest_BOARD, target_profile)
				except Exception as e:
					msg = f'Not able to Pin it -> {e}'
					logit(msg, 1)
			if tumblr:
				logit('Posting on Tumblr')
				try:
					tumblr_post_it(post_content, tumblr_CUSTOMER_KEY, tumblr_CUSTOMER_SECRET, tumblr_OAUTH_TOKEN, tumblr_OAUTH_SECRET)
				except Exception as e:
					msg = f'Not able to Tumblr it -> {e}'
					logit(msg, 1)

		else:
			logit('Noting to do now')

		time.sleep(60*30)



if __name__ == '__main__' :
	main()