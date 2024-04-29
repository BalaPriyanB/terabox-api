from flask import Flask, request, jsonify
from urllib.parse import urlparse, parse_qs
from requests import Session
from http.cookiejar import MozillaCookieJar
from json import loads
from os import path
from re import findall
from time import time
from datetime import datetime
from typing import Dict, Any

app = Flask(__name__)






SIZE_UNITS   = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']

def get_readable_file_size(size_in_bytes):
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    return f'{size_in_bytes:.2f}{SIZE_UNITS[index]}' if index > 0 else f'{size_in_bytes}B'




def direct_link_generator(link: str):
    """ direct links generator """
    domain = urlparse(link).hostname
    if any(x in domain for x in ['terabox', 'nephobox', '4funbox', 'mirrobox', 'momerybox', 'teraboxapp']):
        return terabox(link)
    else:
        return f'No Direct link function found for\n\n{link}\n\nuse /ddllist'


def parseCookieFile(cookiefile: str) -> Dict[str, str]:
    cookies = {}
    with open(cookiefile, 'r') as fp:
        for line in fp:
            if not line.startswith('#'):
                line_fields = line.strip().split('\t')
                if len(line_fields) >= 7:
                    cookie_name = line_fields[5]
                    cookie_value = line_fields[6]
                    cookies[cookie_name] = cookie_value
    return cookies

def __fetch_links(session, dir_: str, folderPath: str, details: Dict[str, Any], jsToken: str, shortUrl: str, cookies: Dict[str, str]):
    params = {
        'app_id': '250528',
        'jsToken': jsToken,
        'shorturl': shortUrl
    }
    if dir_:
        params['dir'] = dir_
    else:
        params['root'] = '1'
    response = session.get("https://www.1024tera.com/share/list", params=params, cookies=cookies)
    data = response.json()
    if data.get('errno') not in [0, '0']:
        if 'errmsg' in data:
            raise DirectDownloadLinkException(data['errmsg'])
        else:
            raise DirectDownloadLinkException('Something went wrong!')
    contents = data.get("list", [])
    for content in contents:
        if content['isdir'] in ['1', 1]:
            newFolderPath = path.join(folderPath, content['server_filename'])
            __fetch_links(session, content['path'], newFolderPath, details, jsToken, shortUrl, cookies)
        else:
            folderPath = details['title'] if details['title'] else ''
            item = {
                'url': content['dlink'],
                'filename': content['server_filename'],
                'path' : path.join(folderPath),
            }
            if 'size' in content:
                size = content["size"]
                if isinstance(size, str) and size.isdigit():
                    size = float(size)
                details['total_size'] += size
            details['contents'].append(item)

@app.route('/terabox', methods=['GET'])
def terabox_download():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL parameter is required'}), 400
    if not path.isfile('/cookies.txt'):
        return jsonify({'error': 'cookies.txt not found'}), 500

    try:
        jar = MozillaCookieJar('/cookies.txt')
        jar.load()
        cookies = {}
        for cookie in jar:
            cookies[cookie.name] = cookie.value
    except Exception as e:
        return jsonify({'error': f"ERROR: {e.__class__.__name__}"}), 500

    details = {'contents':[], 'title': '', 'total_size': 0}
    details["header"] = ' '.join(f'{key}: {value}' for key, value in cookies.items())

    with Session() as session:
        try:
            response = session.get(url, cookies=cookies)
            if jsToken := findall(r'window\.jsToken.*%22(.*)%22', response.text):
                jsToken = jsToken[0]
            else:
                return jsonify({'error': 'jsToken not found'}), 500
            shortUrl = parse_qs(urlparse(response.url).query).get('surl')
            if not shortUrl:
                return jsonify({'error': 'Could not find surl'}), 500
            params = {
                'app_id': '250528',
                'jsToken': jsToken,
                'shorturl': shortUrl
            }
            response = session.get("https://www.1024tera.com/share/list", params=params, cookies=cookies)
            data = response.json()
            if data.get('errno') not in [0, '0']:
                if 'errmsg' in data:
                    return jsonify({'error': data['errmsg']}), 500
                else:
                    return jsonify({'error': 'Something went wrong!'}), 500
            contents = data.get("list", [])
            for content in contents:
                if content['isdir'] in ['1', 1]:
                    newFolderPath = path.join(details['title'], content['server_filename']) if details['title'] else path.join(content['server_filename'])
                    __fetch_links(session, content['path'], newFolderPath, details, jsToken, shortUrl, cookies)
                else:
                    folderPath = details['title'] if details['title'] else ''
                    item = {
                        'url': content['dlink'],
                        'filename': content['server_filename'],
                        'path' : path.join(folderPath),
                    }
                    if 'size' in content:
                        size = content["size"]
                        if isinstance(size, str) and size.isdigit():
                            size = float(size)
                        details['total_size'] += size
                    details['contents'].append(item)
        except Exception as e:
            return jsonify({'error': f'ERROR: {e.__class__.__name__}'}), 500

    file_name = f"[{details['title']}]({url})"
    file_size = details['total_size']
    return jsonify({
        'title': file_name,
        'size': file_size,
        'download_link': details['contents'][0]['url']
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
