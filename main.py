#!/usr/bin/env python3

import os
import time
import tweepy
import filetype
import requests
import pinterest
import pytumblr2
import configparser
from instaloader import *

# import IPython; IPython.embed()
# exit()

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
		line = line.replace('\n', ' ')
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
	if len(post_arr) != 1:
		latest_post = api.user_timeline()[0]
		tweetid = latest_post.id
		screen_name = latest_post.user.screen_name
		for status in post_arr[1:]:
			api.update_status(status=status, in_reply_to_status_id=tweetid)
			time.sleep(5)

	msg = f'New tweet is up -> https://twitter.com/{screen_name}/status/{tweetid}'
	logit(msg, 1)

def tumblr_post_it(post_content, consumer_key, consumer_secret, oauth_token, oauth_secret):
	client = pytumblr2.TumblrRestClient(consumer_key, consumer_secret, oauth_token, oauth_secret)
	account_name = client.info()['user']['name']

	# media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4' or v == 'image/jpeg']

	txt_file_path = [k for k, v in post_content.items() if v == 'plain/text'][0]
	text = ''
	with open(txt_file_path, 'r') as fr:
		for l in fr.readlines():
			if l.strip() != '.':
				text += l

	content = []
	media_sources = {}
	media_count = 0
	for k, v in post_content.items():
		# videos are not implemented yet
		# if v == 'image/jpeg' or v == 'video/mp4':
		if v == 'image/jpeg':
			media_type = v.split('/')[0]
			media_identifier = f'{media_type}_{media_count}'
			media_item = {'type': media_type, 'media': [{'type': v, 'identifier': media_identifier}]}
			if v == 'video/mp4':
				content.insert(0, media_item)
			else:
				content.append(media_item)
			media_sources[media_identifier] = k
			media_count += 1
			if media_count >= 10:
				## media limit per post reached
				break

	content.append({'type': 'text', 'text': text})
	import IPython; IPython.embed()
	exit()
	client.create_post(account_name, content=content, media_sources=media_sources)

	time.sleep(5)

	post_id = client.posts(account_name)['posts'][0]['id']
	msg = f'Tumblr post done -> https://www.tumblr.com/{account_name}/{post_id}'
	logit(msg, 1)

def pin_it(post_content, app_id, app_secret):
	# 500 chars limit
	# 5 files limit
	# https://developers.pinterest.com/docs/content/content-creation/
	p = Api(app_id=app_id, app_secret=app_secret)
	link = pinterest.oauth2.authorization_url(app_id, redirect_uri)
	api = pinterest.Pinterest(token="ApFF9WBrjug_xhJPsETri2jp9pxgFVQfZNayykxFOjJQhWAw")
	api.me()

	if 'video/mp4' in post_content.values():
		media_to_upload = [k for k, v in post_content.items() if v == 'video/mp4']
	else:
		media_to_upload = [k for k, v in post_content.items() if v == 'image/jpeg']

	txt_file_path = [k for k, v in post_content.items() if v == 'plain/text'][0]
	## 500 characters max!! for Insta!
	post_arr = split_text(txt_file_path, 495)

	# 5 files limit
	media_arr = []
	if len(media_to_upload) > 5:
		media_to_upload = media_to_upload[:5]


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
			pin_BOARD_ID = config['Pinterest']['BOARDID']
			pin_APP_ID = config['Pinterest']['APPID']
			pin_APP_SECRET = config['Pinterest']['APPSECRET']
			pin_REFRESHTOKEN = config['Pinterest']['REFRESHTOKEN']
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
			# logit('NOT - DEBUG - Got latest post')
		if new_post:
			logit('Got latest post, posting soon.', 1)
			post_content = file_check(post_fold)

			if tweet:
				logit('Tweeting now!')
				# tweet_it(post_content, twitter_API, twitter_API_SECRET, twitter_TOKEN, twitter_TOKEN_SECRET)
			if pin:
				logit('Posting on Pinterest')
				# pin_it(post_content, pin_APP_ID, pin_APP_SECRET, pin_BOARD_ID)
			if tumblr:
				logit('Posting on Tumblr')
				# tumblr_post_it(post_content, tumblr_CUSTOMER_KEY, tumblr_CUSTOMER_SECRET, tumblr_OAUTH_TOKEN, tumblr_OAUTH_SECRET)

		else:
			logit('Noting to do now')

		time.sleep(60*30)



if __name__ == '__main__' :
	main()