#!/usr/bin/env python3

from rauth import OAuth1Session
from common import API_ORIGIN, get_service, add_auth_params
import sys
import json
import os
import shutil

OUTPUT_DIR = os.path.dirname(__file__) + '/Output/'


# Docs at https://api.smugmug.com/api/v2/doc/tutorial/making-changes.html

def output_request(filename: str, response_json: dict) -> None:
    current_script_directory = os.path.dirname(__file__)
    requests_directory = current_script_directory + '/Requests'
    os.makedirs(requests_directory, exist_ok=True)
    final_filename = requests_directory + '/' + filename + '.json'
    with open(final_filename, 'w') as fh:
        json.dump(response_json, fh, indent=2)


def request(session: OAuth1Session, relative_uri: str) -> dict:
    response = session.get(API_ORIGIN + relative_uri, headers={'Accept': 'application/json'})
    if 200 != response.status_code:
        raise Exception(f"Error fetching {API_ORIGIN + relative_uri}")
    return json.loads(response.text)


def sync_folder_node(session: OAuth1Session, directory_path: str, uri: str) -> None:
    folder_config_path = f"{directory_path}/folder.json"
    if os.path.isfile(folder_config_path):
        print(f"sync_folder_node({directory_path.lstrip(OUTPUT_DIR)}) skipped as already synchronized")
        pass
    else:
        print(f'sync_folder_node({uri}, {directory_path.lstrip(OUTPUT_DIR)})')
        response = request(session, uri)
        output_request('folder_node', response)

        node_type = response['Response']['Node']['Type']
        if 'Folder' != node_type:
            raise Exception(f"Not handling node type of {node_type} for {response['Response']['Node']['UrlPath']}")

        node_id = response['Response']['Node']['NodeID']
        name = response['Response']['Node']['Name']
        description = response['Response']['Node']['Description']
        privacy = response['Response']['Node']['Privacy']
        keywords = response['Response']['Node']['Keywords']
        url_name = response['Response']['Node']['UrlName']
        url_path = response['Response']['Node']['UrlPath']
        date_added = response['Response']['Node']['DateAdded']
        highlight_image_uri = response['Response']['Node']['Uris']['HighlightImage']['Uri']
        node_comments_uri = response['Response']['Node']['Uris']['NodeComments']['Uri']
        child_nodes_uri = response['Response']['Node']['Uris']['ChildNodes']['Uri']

        os.makedirs(directory_path, exist_ok=True)

        config = {
            "node_id": node_id,
            "name": name,
            "description": description,
            "privacy": privacy,
            "keywords": keywords,
            "url_name": url_name,
            "url_path": url_path,
            "date_added": date_added,
            "highlight_image_uri": highlight_image_uri,
            "child_nodes": []
        }

        child_nodes_response = request(session, child_nodes_uri)
        output_request('child_nodes', child_nodes_response)
        child_nodes = child_nodes_response['Response']['Node']
        for child_node in child_nodes:
            child_node_uri = child_node['Uri']
            child_node_node_type = child_node['Type']
            node_id = child_node['NodeID']
            url_name = child_node['UrlName']
            is_root = child_node['IsRoot']
            local_dirname = node_id if len(url_name) == 0 else url_name
            child_directory_path = directory_path + '/' + local_dirname if not is_root else base_directory

            if 'Folder' == child_node_node_type:
                sync_folder_node(session, child_directory_path, child_node_uri)
                config['child_nodes'].append(local_dirname)
            elif 'Album' == child_node_node_type:
                sync_album_node(session, child_directory_path, child_node_uri)
                config['child_nodes'].append(local_dirname)
            else:
                print(f"Unexpected node type '{child_node_node_type}' for child {child_node_uri} in sync_folder_node()")
                exit(44)

        with open(folder_config_path, 'w') as fh:
            json.dump(config, fh, indent=2)


def sync_album_node(session: OAuth1Session, directory_path: str, uri: str) -> None:
    album_config_filename = f"{directory_path}/album.json"
    if os.path.isfile(album_config_filename):
        print(f"sync_album_node({uri}) skipped as already synchronized")
        pass
    else:
        print(f'sync_album_node({uri}, {directory_path.lstrip(OUTPUT_DIR)})')
        response = request(session, uri)
        output_request('album_node', response)

        node_type = response['Response']['Node']['Type']
        if 'Album' != node_type:
            raise Exception(f"Not handling node type of {node_type} for {response['Response']['Node']['UrlPath']}")

        node_id = response['Response']['Node']['NodeID']
        name = response['Response']['Node']['Name']
        description = response['Response']['Node']['Description']
        privacy = response['Response']['Node']['Privacy']
        keywords = response['Response']['Node']['Keywords']
        url_name = response['Response']['Node']['UrlName']
        url_path = response['Response']['Node']['UrlPath']
        date_added = response['Response']['Node']['DateAdded']
        highlight_image_uri = response['Response']['Node']['Uris']['HighlightImage']['Uri']
        node_comments_uri = response['Response']['Node']['Uris']['NodeComments']['Uri']
        album_uri = response['Response']['Node']['Uris']['Album']['Uri']

        os.makedirs(directory_path, exist_ok=True)

        config = {
            "node_id": node_id,
            "name": name,
            "description": description,
            "privacy": privacy,
            "keywords": keywords,
            "url_name": url_name,
            "url_path": url_path,
            "date_added": date_added,
            "highlight_image_uri": highlight_image_uri,
            "images": []
        }

        album_response = request(session, album_uri)
        output_request('album', album_response)

        album_images_uri = album_response['Response']['Album']['Uris']['AlbumImages']['Uri']
        album_images_response = request(session, album_images_uri)
        output_request('album_images', album_images_response)

        album_images = album_images_response['Response']['AlbumImage']
        for album_image in album_images:
            config['images'].append(album_image['ImageKey'])

        for album_image in album_images:
            sync_album_image(session, directory_path, album_image)

        with open(album_config_filename, 'w') as fh:
            json.dump(config, fh, indent=2)


def sync_album_image(session: OAuth1Session, base_directory: str, image_data: dict) -> None:
    image_key = image_data['ImageKey']
    image_config_filename = f"{base_directory}/{image_key}.json"
    if os.path.isfile(image_config_filename):
        print(f"sync_album_image({image_key}) skipped as already synchronized")
        pass
    else:
        print(f'sync_album_image({image_key})')

        config = {
            'image_key': image_data['ImageKey'],
            'title': image_data['Title'],
            'caption': image_data['Caption'],
            'keywords': image_data['KeywordArray'],
            'latitude': image_data['Latitude'],
            'longitude': image_data['Longitude'],
            'altitude': image_data['Altitude'],
            'hidden': image_data['Hidden'],
            'filename': image_data['FileName'],
            'date_time_original': image_data['DateTimeOriginal'],
            'date_time_uploaded': image_data['DateTimeUploaded'],
            'original_height': image_data['OriginalHeight'],
            'original_width': image_data['OriginalWidth'],
            'original_size': image_data['OriginalSize'],
            'images': [],
        }

        thumbnail_url = image_data['ThumbnailUrl']
        extension = image_data['Format'].lower()
        fetch_image(session, base_directory, image_key, extension, thumbnail_url, 'Th', 'Thumbnail')

        image_sizes_uri = image_data['Uris']['ImageSizes']['Uri']
        image_sizes_response = request(session, image_sizes_uri)
        output_request('image_sizes', image_sizes_response)
        images_sizes_data = image_sizes_response['Response']['ImageSizes']
        if 'TinyImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['TinyImageUrl'],
                                   'Ti', 'Tiny')
            config['images'].append(os.path.basename(filename))
        if 'ThumbImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['ThumbImageUrl'],
                                   'Th', 'Thumbnail')
            config['images'].append(os.path.basename(filename))
        if 'SmallImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['SmallImageUrl'],
                                   'S', 'Small')
            config['images'].append(os.path.basename(filename))
        if 'MediumImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['MediumImageUrl'],
                                   'M', 'Medium')
            config['images'].append(os.path.basename(filename))
        if 'LargeImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['LargeImageUrl'],
                                   'L', 'Large')
            config['images'].append(os.path.basename(filename))
        if 'XLargeImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['XLargeImageUrl'],
                                   'XL', 'XLarge')
            config['images'].append(os.path.basename(filename))
        if 'X2LargeImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['X2LargeImageUrl'],
                                   'X2', 'X2Large')
            config['images'].append(os.path.basename(filename))
        if 'X3LargeImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['X3LargeImageUrl'],
                                   'X3', 'X3Large')
            config['images'].append(os.path.basename(filename))
        if 'OriginalImageUrl' in images_sizes_data:
            filename = fetch_image(session, base_directory, image_key, extension, images_sizes_data['OriginalImageUrl'],
                                   'Original', 'Original')
            config['images'].append(os.path.basename(filename))

        with open(image_config_filename, 'w') as fh:
            json.dump(config, fh, indent=2)


def fetch_image(session: OAuth1Session,
                base_directory: str,
                image_key: str,
                extension: str,
                url: str,
                size: str,
                size_label: str) -> str:
    image_filename = f"{base_directory}/{image_key}-{size}.{extension}"
    if not os.path.isfile(image_filename):
        data = session.get(url, stream=True)
        if 200 != data.status_code:
            raise Exception(f"Error fetching {size_label} image for {image_key} @ {url}")

        data.raw.decode_content = True
        with open(image_filename + '.tmp', 'wb') as fh:
            shutil.copyfileobj(data.raw, fh)
        del data
        os.rename(image_filename + '.tmp', image_filename)

        print(f'Downloading {size_label} => {image_filename.lstrip(OUTPUT_DIR)}')
    return image_filename


def main():
    """This example interacts with its user through the console, but it is
    similar in principle to the way any non-web-based application can obtain an
    OAuth authorization from a user."""
    service = get_service()

    access_token = None
    access_token_secret = None
    config = None

    # Try to load auth tokens from config if present, otherwise next step will generate them
    try:
        with open('config.json', 'r') as fh:
            config = json.load(fh)
    except IOError as e:
        print('====================================================')
        print('Failed to open config.json! Did you create it?')
        print('The expected format is demonstrated in example.json.')
        print('====================================================')
        sys.exit(1)

    if type(config) is dict \
            and 'access-token' in config \
            and 'access-token-secret' in config \
            and type(config['access-token']) is str \
            and type(config['access-token-secret']) is str:
        access_token = config['access-token']
        access_token_secret = config['access-token-secret']

    if not access_token or not access_token_secret:
        # First, we need a request token and secret, which SmugMug will give us.
        # We are specifying "oob" (out-of-band) as the callback because we don't
        # have a website for SmugMug to call back to.
        rt, rts = service.get_request_token(params={'oauth_callback': 'oob'})

        # Second, we need to give the user the web URL where they can authorize our
        # application.
        auth_url = add_auth_params(service.get_authorize_url(rt), access='Full', permissions='Modify')
        print('Go to %s in a web browser.' % auth_url)

        # Once the user has authorized our application, they will be given a
        # six-digit verifier code. Our third step is to ask the user to enter that
        # code:
        sys.stdout.write('Enter the six-digit code: ')
        sys.stdout.flush()
        verifier = sys.stdin.readline().strip()

        # Finally, we can use the verifier code, along with the request token and
        # secret, to sign a request for an access token.
        access_token, access_token_secret = service.get_access_token(rt, rts, params={'oauth_verifier': verifier})

        print('Created new access token...')
        print('Access token: %s' % access_token)
        print('Access token secret: %s' % access_token_secret)

        with open('config.json', 'w') as fh:
            config = {
                "key": config["key"],
                "secret": config["secret"],
                "access-token": access_token,
                "access-token-secret": access_token_secret
            }
            json.dump(config, fh)

    # The access token we have received is valid forever, unless the user
    # revokes it.  Let's make one example API request to show that the access
    # token works.
    session = OAuth1Session(service.consumer_key, service.consumer_secret, access_token=access_token,
                            access_token_secret=access_token_secret)

    user = request(session, '/api/v2!authuser')
    # output_request('user', user)

    sync_folder_node(session,
                     OUTPUT_DIR + user['Response']['User']['Name'],
                     user['Response']['User']['Uris']['Node']['Uri'])


if __name__ == '__main__':
    main()
