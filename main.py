import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from cache_gen import cache_gen
from config_manager import ProfileError, discover_profiles, load_profile
from csv_gen import csv_gen
from md_gen import md_gen
from timeline_utils import evaluate_time_window
from url_utils import quote_url
from user_info import User_info


class MediaNotFoundError(Exception):
    """Raised when an original media variant is unavailable."""


def select_settings_file(requested_file=None):
    """选择要使用的 settings 文件"""
    if requested_file:
        requested_name = Path(requested_file).name
        print(f"使用配置文件: {requested_name}\n")
        return requested_name

    profiles = discover_profiles()
    settings_files = [profile["filename"] for profile in profiles]
    if not settings_files:
        print("错误: 未找到任何 settings 文件")
        sys.exit(1)
    if len(settings_files) == 1:
        print(f"使用配置文件: {settings_files[0]}\n")
        return settings_files[0]
    print("=" * 60)
    print("发现多个配置文件，请选择要使用的配置：")
    print("=" * 60)
    settings_files.sort()
    profile_lookup = {profile["filename"]: profile for profile in profiles}
    for idx, filename in enumerate(settings_files, 1):
        profile = profile_lookup[filename]
        users = ", ".join(profile["users"]) or "未设置"
        suffix = f"用户: {users}" if profile["valid"] else f"配置错误: {profile['error']}"
        print(f"{idx}. {filename:<30} ({suffix})")
    print("=" * 60)
    while True:
        try:
            choice = input(f"请选择配置文件 (1-{len(settings_files)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(settings_files):
                selected_file = settings_files[choice_num - 1]
                print(f"\n已选择: {selected_file}\n")
                return selected_file
            else:
                print(f"请输入 1 到 {len(settings_files)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n已取消")
            sys.exit(0)

def extract_resource_filename(url):
    """从URL中提取服务器文件名（不含扩展名和参数）"""
    return Path(urlsplit(url).path).stem

def del_special_char(string):
    string = re.sub(r'[^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\u3040-\u31FF\.]', '', string)
    return string

def stamp2time(msecs_stamp:int) -> str:
    timeArray = time.localtime(msecs_stamp/1000)
    otherStyleTime = time.strftime("%Y-%m-%d %H-%M", timeArray)
    return otherStyleTime

def time2stamp(timestr:str) -> int:
    datetime_obj = datetime.strptime(timestr, "%Y-%m-%d").astimezone()
    msecs_stamp = int(datetime_obj.timestamp() * 1000)
    return msecs_stamp

def time_comparison(now, start, end):
    return evaluate_time_window(
        now,
        start,
        end,
        ordered_by_tweet_time=not has_likes,
    )
    

#读取配置
log_output = False
has_retweet = False
has_highlights = False
has_likes = False
has_video = False
csv_file = None
cache_data = None
down_log = False
autoSync = False

md_file = None
md_output = True
media_count_limit = 0

start_time_stamp = 655028357000   #1990-10-04
end_time_stamp = 2548484357000    #2050-10-04
start_label = True
First_Page = True       #首页提取内容时特殊处理

# 选择并校验配置文件
argument_parser = argparse.ArgumentParser(description="下载 X/Twitter 用户媒体")
argument_parser.add_argument("-c", "--config", help="要使用的 settings*.json 配置文件")
arguments = argument_parser.parse_args()
settings_file = select_settings_file(arguments.config)

try:
    settings = load_profile(settings_file, require_runtime=True)
except ProfileError as exc:
    print(f"配置错误: {exc}")
    raise SystemExit(2) from exc

settings['save_path'] = str(Path(settings['save_path']).expanduser().resolve()) if settings['save_path'] else os.getcwd()
if settings:
    if settings['has_retweet']:
        has_retweet = True
    if settings['high_lights']:
        has_highlights = True
        has_retweet = False
    if settings['time_range']:
        time_range = True
        start_time,end_time = settings['time_range'].split(':')
        start_time_stamp,end_time_stamp = time2stamp(start_time),time2stamp(end_time)
    if settings['autoSync']:
        autoSync = True
    if settings['down_log']:
        down_log = True
    share_cache = settings.get('share_cache', False)
    if settings['likes']:   #likes的逻辑和retweet大致相同
        has_retweet = True
        has_likes = True
        has_highlights = False
    if settings['has_video']:
        has_video = True
    if settings['log_output']:
        log_output = True
    max_concurrent_requests = settings['max_concurrent_requests']
    ###### proxy ######
    proxies = settings['proxy'] or None

############
    if settings['image_format'] == 'orig':
        orig_format = True
        img_format = 'jpg'
    else:
        orig_format = False
        img_format = settings['image_format']

    if not settings['md_output']:
        md_output = False

    if settings['media_count_limit']:
        media_count_limit = settings['media_count_limit']

backup_stamp = start_time_stamp

_headers = {
    'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'authorization':'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
}
_headers['cookie'] = settings['cookie']

request_count = 0    #请求次数计数
down_count = 0      #下载图片数计数

def get_other_info(_user_info):
    url = 'https://twitter.com/i/api/graphql/xc8f1g7BYqr6VTzTbvNlGw/UserByScreenName?variables={"screen_name":"' + _user_info.screen_name + '","withSafetyModeUserFields":false}&features={"hidden_profile_likes_enabled":false,"hidden_profile_subscriptions_enabled":false,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"subscriptions_verification_info_verified_since_enabled":true,"highlights_tweets_tab_ui_enabled":true,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"responsive_web_graphql_timeline_navigation_enabled":true}&fieldToggles={"withAuxiliaryUserLabels":false}'
    response = ""
    try:
        global request_count
        http_response = httpx.get(quote_url(url), headers=_headers, proxy=proxies)
        http_response.raise_for_status()
        response = http_response.text
        request_count += 1
        raw_data = json.loads(response)
        _user_info.rest_id = raw_data['data']['user']['result']['rest_id']
        _user_info.name = raw_data['data']['user']['result']['legacy']['name']
        _user_info.statuses_count = raw_data['data']['user']['result']['legacy']['statuses_count']
        _user_info.media_count = raw_data['data']['user']['result']['legacy']['media_count']
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError) as e:
        print('获取信息失败')
        print(e)
        print(response)
        return False
    return True

def print_info(_user_info):
    print(
        f'''
        <======基本信息=====>
        昵称:{_user_info.name.encode('utf-8', errors='replace').decode('utf-8')}
        用户名:{_user_info.screen_name}
        数字ID:{_user_info.rest_id}
        总推数(含转推):{_user_info.statuses_count}
        含图片/视频/音频推数(不含转推):{_user_info.media_count}
        <==================>
        开始爬取...
        '''
    )

def get_download_url(_user_info):

    def get_heighest_video_quality(variants) -> str:   #找到最高质量的视频地址,并返回

        if len(variants) == 1:      #gif适配
            return variants[0]['url']
        
        max_bitrate = 0
        heighest_url = None
        for i in variants:
            if 'bitrate' in i and int(i['bitrate']) > max_bitrate:
                max_bitrate = int(i['bitrate'])
                heighest_url = i['url']
        return heighest_url


    def get_url_from_content(content):
        global start_label
        _photo_lst = []
        x_label = 'content' if has_retweet or has_highlights else 'item'
        for i in content:
            try:
                if 'promoted-tweet' in i['entryId']:        #排除广告
                    continue
                if 'tweet' in i['entryId']:     #正常推文
                    if 'tweet' in i[x_label]['itemContent']['tweet_results']['result']:
                        a = i[x_label]['itemContent']['tweet_results']['result']['tweet']['legacy']       #适配限制回复账号
                        author_screen_name = i[x_label]['itemContent']['tweet_results']['result']['tweet']['core']['user_results']['result']['legacy']['screen_name']
                        frr = [a['favorite_count'], a['retweet_count'], a['reply_count']]
                        tweet_msecs = int(i[x_label]['itemContent']['tweet_results']['result']['tweet']['edit_control']['editable_until_msecs']) - 3600000
                    else:
                        a = i[x_label]['itemContent']['tweet_results']['result']['legacy']
                        author_screen_name = i[x_label]['itemContent']['tweet_results']['result']['core']['user_results']['result']['legacy']['screen_name']
                        frr = [a['favorite_count'], a['retweet_count'], a['reply_count']]
                        tweet_msecs = int(i[x_label]['itemContent']['tweet_results']['result']['edit_control']['editable_until_msecs']) - 3600000
                    timestr = stamp2time(tweet_msecs)

                    #我知道这边代码很烂
                    #但我实在不想重构 ( º﹃º )

                    _result = time_comparison(tweet_msecs, start_time_stamp, end_time_stamp)
                    if _result[0]:  #符合时间限制
                        if 'retweeted_status_result' not in a : #判断是否为转推,以及是否获取转推
                            name = _user_info.name
                            screen_name = _user_info.screen_name
                            if has_likes:
                                a2 = i[x_label]['itemContent']['tweet_results']['result']['core']['user_results']['result']['legacy']
                                name = a2['name']
                                screen_name = a2['screen_name']
                            if 'extended_entities' in a:
                                _photo_lst += [(get_heighest_video_quality(_media['video_info']['variants']), f'{timestr}_@{author_screen_name}-vid', [tweet_msecs, name, f'@{screen_name}', _media['expanded_url'], 'Video', get_heighest_video_quality(_media['video_info']['variants']), '', a['full_text']] + frr) if 'video_info' in _media and has_video else (_media['media_url_https'], f'{timestr}_@{author_screen_name}-img', [tweet_msecs, name, f'@{screen_name}', _media['expanded_url'], 'Image', _media['media_url_https'], '', a['full_text']] + frr) for _media in a['extended_entities']['media']]

                        elif has_retweet:
                            name = a['retweeted_status_result']['result']['core']['user_results']['result']['legacy']['name']
                            screen_name = a['retweeted_status_result']['result']['core']['user_results']['result']['legacy']['screen_name']
                            full_text = a['retweeted_status_result']['result']['legacy']['full_text']
                            if 'extended_entities' in a['retweeted_status_result']['result']['legacy'] and screen_name != _user_info.screen_name:
                                _photo_lst += [(get_heighest_video_quality(_media['video_info']['variants']), f'{timestr}_@{screen_name}-vid-retweet', [tweet_msecs, name, f"@{screen_name}", _media['expanded_url'], 'Video', get_heighest_video_quality(_media['video_info']['variants']), '', full_text] + frr) if 'video_info' in _media and has_video else (_media['media_url_https'], f'{timestr}_@{screen_name}-img-retweet', [tweet_msecs, name, f"@{screen_name}", _media['expanded_url'], 'Image', _media['media_url_https'], '', full_text] + frr) for _media in a['retweeted_status_result']['result']['legacy']['extended_entities']['media']]

                    elif not _result[1]:    #已超出目标时间范围
                        start_label = False
                        break
                
                elif 'profile-conversation' in i['entryId']:    #回复的推文(对话线索)
                    if 'tweet' in i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']:
                        a = i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']['tweet']['legacy']
                        author_screen_name = i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']['tweet']['core']['user_results']['result']['legacy']['screen_name']
                        frr = [a['favorite_count'], a['retweet_count'], a['reply_count']]
                        tweet_msecs = int(i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']['tweet']['edit_control']['editable_until_msecs']) - 3600000
                    else:
                        a = i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']['legacy']
                        author_screen_name = i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']['core']['user_results']['result']['legacy']['screen_name']
                        frr = [a['favorite_count'], a['retweet_count'], a['reply_count']]
                        tweet_msecs = int(i[x_label]['items'][0]['item']['itemContent']['tweet_results']['result']['edit_control']['editable_until_msecs']) - 3600000
                    timestr = stamp2time(tweet_msecs)

                    _result = time_comparison(tweet_msecs, start_time_stamp, end_time_stamp)
                    if _result[0]:  #符合时间限制
                        if 'extended_entities' in a:
                            _photo_lst += [(get_heighest_video_quality(_media['video_info']['variants']), f'{timestr}_@{author_screen_name}-vid', [tweet_msecs, _user_info.name, f'@{_user_info.screen_name}', _media['expanded_url'], 'Video', get_heighest_video_quality(_media['video_info']['variants']), '', a['full_text']] + frr) if 'video_info' in _media and has_video else (_media['media_url_https'], f'{timestr}_@{author_screen_name}-img', [tweet_msecs, _user_info.name, f'@{_user_info.screen_name}', _media['expanded_url'], 'Image', _media['media_url_https'], '', a['full_text']] + frr) for _media in a['extended_entities']['media']]
                    elif not _result[1]:    #已超出目标时间范围
                        start_label = False
                        break

            except (KeyError, IndexError, TypeError, ValueError) as exc:
                if log_output:
                    print(f"跳过无法解析的时间线条目: {exc}")
                continue
            if 'cursor-bottom' in i['entryId']:     #更新下一页的请求编号(含转推模式&亮点模式)
                _user_info.cursor = i['content']['value']

        return _photo_lst

    print(f'已下载图片/视频:{_user_info.count}')
    if has_highlights: ##2024-01-05 #适配[亮点]标签
        url_top = 'https://twitter.com/i/api/graphql/w9-i9VNm_92GYFaiyGT1NA/UserHighlightsTweets?variables={"userId":"' + _user_info.rest_id + '","count":20,'
        url_bottom = '"includePromotedContent":true,"withVoice":true}&features={"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}'
    elif has_likes:
        url_top = 'https://twitter.com/i/api/graphql/-fbTO1rKPa3nO6-XIRgEFQ/Likes?variables={"userId":"' + _user_info.rest_id + '","count":200,'
        url_bottom = '"includePromotedContent":false,"withClientEventToken":false,"withBirdwatchNotes":false,"withVoice":true,"withV2Timeline":true}&features={"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}'
    elif has_retweet:     #包含转推调用[UserTweets]的API(调用一次上限返回20条)
        url_top = 'https://twitter.com/i/api/graphql/2GIWTr7XwadIixZDtyXd4A/UserTweets?variables={"userId":"' + _user_info.rest_id + '","count":20,'
        url_bottom = '"includePromotedContent":false,"withQuickPromoteEligibilityTweetFields":true,"withVoice":true,"withV2Timeline":true}&features={"rweb_lists_timeline_redesign_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}&fieldToggles={"withAuxiliaryUserLabels":false,"withArticleRichContentState":false}'
    else:       #不包含转推则调用[UserMedia]的API(返回条数貌似无上限/改count) ##2023-12-11#此模式API返回值变动
        url_top = 'https://twitter.com/i/api/graphql/Le6KlbilFmSu-5VltFND-Q/UserMedia?variables={"userId":"' + _user_info.rest_id + '","count":500,'
        url_bottom = '"includePromotedContent":false,"withClientEventToken":false,"withBirdwatchNotes":false,"withVoice":true,"withV2Timeline":true}&features={"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false}'

    url = url_top + '"cursor":"' + _user_info.cursor + '",' + url_bottom if _user_info.cursor else url_top + url_bottom
    response = ""
    try:
        global request_count
        http_response = httpx.get(quote_url(url), headers=_headers, proxy=proxies)
        http_response.raise_for_status()
        response = http_response.text
        request_count += 1
        try:
            raw_data = json.loads(response)
        except json.JSONDecodeError:
            if 'Rate limit exceeded' in response:
                print('API次数已超限')
            else:
                print('获取数据失败')
            print(response)
            return
        if has_highlights:  #亮点模式
            raw_data = raw_data['data']['user']['result']['timeline']['timeline']['instructions'][-1]['entries']
        elif has_retweet:   #与likes共用
            raw_data = raw_data['data']['user']['result']['timeline_v2']['timeline']['instructions'][-1]['entries']
        else:   #usermedia模式
            raw_data = raw_data['data']['user']['result']['timeline_v2']['timeline']['instructions']
        if (has_retweet or has_highlights) and 'cursor-top' in raw_data[0]['entryId']:      #含转推模式 所有推文已全部下载完成
            return False
        
        if not has_retweet and not has_highlights:     #usermedia模式下的下一页请求编号
            for i in raw_data[-1]['entries']:
                if 'bottom' in i['entryId']:
                    _user_info.cursor = i['content']['value']
            # _user_info.cursor = raw_data[-1]['entries'][0]['content']['value']
        
        if start_label:     #判断是否超出时间范围
            if not has_retweet and not has_highlights:
                global First_Page
                if First_Page:   #第一页的返回值需特殊处理
                    raw_data = raw_data[-1]['entries'][0]['content']['items']
                    First_Page = False
                else:
                    if 'moduleItems' not in raw_data[0]:    #usermedia新模式，所有推文已全部下载完成
                        return False
                    else:
                        raw_data = raw_data[0]['moduleItems']
            photo_lst = get_url_from_content(raw_data)
        else:
            return False
        
        if not photo_lst:
            photo_lst.append(True)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
        print('获取推文信息错误')
        print(e)
        print(response)
        return False
    return photo_lst

def download_control(_user_info):
    async def _main():
        async def down_save(url, prefix, csv_info, order: int):
            # 保存原始URL用于缓存（去除参数）
            original_url = url.split('?', 1)[0] if '?' in url else url

            # 使用服务器文件名
            filename = extract_resource_filename(url)

            if '.mp4' in url:
                _file_name = f'{_user_info.save_path + os.sep}{prefix}_{filename}.mp4'
                # if os.path.exists(_file_name):
                #     if log_output:
                #         print(f'{_file_name} 已存在，跳过')
                #     if down_log:
                #         cache_data.add(original_url)
                #     return False
            else:
                try:
                    if orig_format:
                        url += '?name=orig'
                        _file_name = f'{_user_info.save_path + os.sep}{prefix}_{filename}.{csv_info[5][-3:]}' # 根据图片 url 获取原始格式
                    else: # 指定格式时，先使用 name=orig，404 则切回 name=4096x4096，以保证最大尺寸
                        _file_name = f'{_user_info.save_path + os.sep}{prefix}_{filename}.{img_format}'
                        if img_format != 'png':
                            url += '?format=jpg&name=4096x4096'
                        else:
                            url += '?format=png&name=4096x4096'
                    # if os.path.exists(_file_name):
                    #     if log_output:
                    #         print(f'{_file_name} 已存在，跳过')
                    #     if down_log:
                    #         cache_data.add(original_url)
                    #     return False
                except (KeyError, IndexError, TypeError):
                    print(url)
                    return False

            csv_info[-5] = os.path.split(_file_name)[1]
            if md_output: # 在下载完毕之前先输出到 Markdown，以尽可能保证高并发下载也能得到正确的推文顺序。
                md_file.media_tweet_input(csv_info, prefix)
            count = 0
            while True:
                try:
                    async with semaphore:
                        global down_count
                        response = await client.get(quote_url(url))
                        if response.status_code == 404:
                            raise MediaNotFoundError
                        response.raise_for_status()
                        down_count += 1
                    await asyncio.to_thread(Path(_file_name).write_bytes, response.content)

                    csv_file.data_input(csv_info)

                    if log_output:
                        print(f'{_file_name}=====>下载完成')

                    # 下载完成后保存缓存
                    if down_log:
                        metadata = {
                            'url': original_url,
                            'tweet_time': csv_info[0],
                            'author_screen_name': csv_info[2],
                            'author_name': csv_info[1],
                            'tweet_url': csv_info[3],
                            'media_type': csv_info[4],
                            'tweet_text': csv_info[7]
                        }
                        cache_data.add(filename, metadata)

                    break
                except (httpx.HTTPError, OSError, MediaNotFoundError) as exc:
                    if '.mp4' in url or orig_format or not isinstance(exc, MediaNotFoundError):
                        count += 1
                        if count >= 50:
                            print(f'{_file_name}=====>第{count}次下载失败，已跳过该文件。')
                            print(url)
                            break
                        print(f'{_file_name}=====>第{count}次下载失败,正在重试')
                        print(url)
                        await asyncio.sleep(min(0.25 * (2 ** min(count, 5)), 5))
                    else:
                        url = url.replace('name=orig', 'name=4096x4096')

        timeout = httpx.Timeout(16, connect=3.05)
        async with httpx.AsyncClient(proxy=proxies, timeout=timeout, follow_redirects=True) as client:
            while True:
                photo_lst = get_download_url(_user_info)
                if not photo_lst:
                    break
                elif photo_lst[0] is True:
                    continue
                semaphore = asyncio.Semaphore(max_concurrent_requests)    #最大并发数量，默认为8，对自己网络有自信的可以调高
                if down_log:
                    # 检查缓存时使用 file_hash
                    await asyncio.gather(*[asyncio.create_task(down_save(url[0], url[1], url[2], order)) for order,url in enumerate(photo_lst) if cache_data.should_download(extract_resource_filename(url[0]))])
                else:
                    await asyncio.gather(*[asyncio.create_task(down_save(url[0], url[1], url[2], order)) for order,url in enumerate(photo_lst)])
                _user_info.count += len(photo_lst)      #更新计数

    asyncio.run(_main())

def main(_user_info: object):
    re_token = 'ct0=(.*?);'
    _headers['x-csrf-token'] = re.findall(re_token,_headers['cookie'])[0]
    _headers['referer'] = 'https://twitter.com/' + _user_info.screen_name
    if not get_other_info(_user_info):
        return False
    print_info(_user_info)
    output_path = Path(settings['save_path']) / _user_info.screen_name
    output_path.mkdir(parents=True, exist_ok=True)
    _user_info.save_path = str(output_path)

    global csv_file
    csv_file = csv_gen(_user_info.save_path, _user_info.name, _user_info.screen_name, settings['time_range'])

    if md_output:
        global md_file
        md_file = md_gen(_user_info.save_path, _user_info.name, _user_info.screen_name, settings['time_range'], has_likes, media_count_limit)

    if down_log:
        global cache_data
        cache_data = cache_gen(_user_info.save_path, is_share=share_cache)

    if autoSync:
        files = sorted(os.listdir(_user_info.save_path))
        if len(files) > 0:
            global start_time_stamp
            re_rule = r'\d{4}-\d{2}-\d{2}'
            for i in files[::-1]:
                if "-img_" in i or "-vid_" in i:
                    start_time_stamp = time2stamp(re.findall(re_rule, i)[0])
                    break
                else:
                    start_time_stamp = backup_stamp
        else:
            start_time_stamp = backup_stamp

    try:
        download_control(_user_info)
    finally:
        csv_file.csv_close()
        if md_output:
            md_file.md_close()
        if down_log:
            cache_data.close()
    print(f'{_user_info.name}下载完成\n\n')

if __name__ == '__main__':
    _start = time.time()
    for screen_name in settings['user_lst'].split(','):
        main(User_info(screen_name))
        start_label = True
        First_Page = True
    print(f'共耗时:{time.time()-_start}秒\n共调用{request_count}次API\n共下载{down_count}份图片/视频')
