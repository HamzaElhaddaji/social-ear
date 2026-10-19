"""Explicit, user-triggered collection from a fixed public Bluesky endpoint."""
import time
import os
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlencode
import httpx


def request_json(url, params=None, headers=None):
    for attempt in range(3):
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=20, follow_redirects=False)
        except httpx.TransportError:
            if attempt < 2:
                time.sleep(2**attempt); continue
            raise ValueError('The social provider could not be reached. Try again later.') from None
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 2:
                time.sleep(2**attempt); continue
        if response.status_code != 200:
            raise ValueError(f'Social provider returned HTTP {response.status_code}. Check API access, credentials, permissions and quota.')
        try:
            return response.json()
        except ValueError:
            raise ValueError('Social provider returned an invalid response.') from None
    raise ValueError('Social provider retries exhausted.')


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.suppressed=0

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.suppressed+=1
        if tag in ('p','br','div'): self.parts.append('\n')
        if tag=='img' and not self.suppressed:
            self.parts.append(dict(attrs).get('alt',''))

    def handle_endtag(self, tag):
        if tag in ('script','style') and self.suppressed: self.suppressed-=1
        if tag in ('p','div'): self.parts.append('\n')

    def handle_data(self, data):
        if not self.suppressed:self.parts.append(data)


def mastodon(hashtag):
    tag=hashtag.lstrip('#')
    if not re.fullmatch(r'\w{1,80}',tag):
        raise ValueError('Use one hashtag containing only letters, numbers or underscores.')
    token=os.environ.get('MASTODON_TOKEN','')
    data=request_json('https://mastodon.social/api/v1/timelines/tag/'+quote(tag,safe=''), params={'limit':40},
                      headers={'Authorization':'Bearer '+token} if token else None)
    if not isinstance(data,list):raise ValueError('Mastodon returned an unexpected response.')
    result=[]
    for post in data:
        if post.get('visibility')!='public':continue
        parser=PlainText();parser.feed(post.get('content',''))
        result.append({'text':''.join(parser.parts).strip(),'source':'Mastodon',
                       'published_at':post.get('created_at',''),'url':post.get('url',''),'remote_id':str(post.get('id',''))})
    return result


def youtube(video_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id):raise ValueError('Enter an 11-character YouTube video ID.')
    key=os.environ.get('YOUTUBE_API_KEY','')
    if not key:raise ValueError('YouTube API key is not configured on the server.')
    data=request_json('https://www.googleapis.com/youtube/v3/commentThreads',
                      params={'part':'snippet','videoId':video_id,'maxResults':100,'textFormat':'plainText','order':'time','key':key})
    if not isinstance(data,dict) or not isinstance(data.get('items'),list):raise ValueError('YouTube returned an unexpected response.')
    result=[]
    for item in data['items']:
        comment=item.get('snippet',{}).get('topLevelComment',{})
        snippet=comment.get('snippet',{})
        identity=str(comment.get('id',''))
        result.append({'text':snippet.get('textOriginal',snippet.get('textDisplay','')),'source':'YouTube',
                       'published_at':snippet.get('publishedAt',''),'remote_id':identity,
                       'url':'https://www.youtube.com/watch?'+urlencode({'v':video_id,'lc':identity})})
    return result


def bluesky(query):
    for attempt in range(3):
        response = httpx.get('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',
                             params={'q': query, 'limit': 100, 'sort': 'latest'},
                             timeout=20, follow_redirects=False)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
        if response.status_code != 200:
            raise ValueError(f'Bluesky returned HTTP {response.status_code}. Public search availability depends on the provider; CSV imports remain available.')
        return [{'text': p.get('record', {}).get('text', ''), 'source': 'Bluesky',
                 'published_at': p.get('record', {}).get('createdAt', '')} for p in response.json().get('posts', [])]
    return []
