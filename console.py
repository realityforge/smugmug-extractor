#!/usr/bin/env python3
import typing

from rauth import OAuth1Session
import sys

from common import API_ORIGIN, get_service, add_auth_params
import json
import os


# Docs at https://api.smugmug.com/api/v2/doc/tutorial/making-changes.html

def output_request(filename: str, response_json: dict):
    current_script_directory = os.path.dirname(__file__)
    requests_directory = current_script_directory + '/Requests'
    os.makedirs(requests_directory, exist_ok=True)
    final_filename = requests_directory + '/' + filename + '.json'
    with open(final_filename, 'w') as fh:
        json.dump(response_json, fh, indent=2)


def request(session: OAuth1Session, relative_uri: str) -> dict:
    data = session.get(API_ORIGIN + relative_uri, headers={'Accept': 'application/json'}).text
    return json.loads(data)


def sync_directory_node(session: OAuth1Session, base_directory: str, uri: str):
    print(f'sync_directory_node({uri}, {base_directory})')
    response = request(session, uri)
    output_request('node', response)

    node_id = response['Response']['Node']['NodeID']
    name = response['Response']['Node']['Name']
    description = response['Response']['Node']['Description']
    privacy = response['Response']['Node']['Privacy']
    keywords = response['Response']['Node']['Keywords']
    node_type = response['Response']['Node']['Type']
    url_name = response['Response']['Node']['UrlName']
    url_path = response['Response']['Node']['UrlPath']
    date_added = response['Response']['Node']['DateAdded']
    highlight_image_uri = response['Response']['Node']['Uris']['HighlightImage']['Uri']
    node_comments_uri = response['Response']['Node']['Uris']['NodeComments']['Uri']
    child_nodes_uri = response['Response']['Node']['Uris']['ChildNodes']['Uri']

    if node_type != 'Folder':
        print(f"Not handling node type of {node_type} for {url_path}")
        return

    local_dirname = node_id if len(url_name) == 0 else url_name
    directory_path = base_directory + '/' + local_dirname
    os.makedirs(directory_path, exist_ok=True)

    folder_config = {
        "node_id": node_id,
        "name": name,
        "description": description,
        "privacy": privacy,
        "keywords": keywords,
        "url_name": url_name,
        "url_path": url_path,
        "date_added": date_added,
        "highlight_image_uri": highlight_image_uri
    }
    with open(f"{directory_path}/folder.json", 'w') as fh:
        json.dump(folder_config, fh, indent=2)

    child_nodes_response = request(session, child_nodes_uri)
    output_request('child_nodes', child_nodes_response)
    child_nodes = child_nodes_response['Response']['Node']
    for child_node in child_nodes:
        child_node_uri = child_node['Uri']
        child_node_node_type = child_node['Type']
        if 'Folder' == child_node_node_type:
            sync_directory_node(session, directory_path, child_node_uri)
            pass


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

    account_name = user['Response']['User']['Name']

    current_script_directory = os.path.dirname(__file__)
    output_dir = current_script_directory + '/Output/' + account_name

    root_node_endpoint = user['Response']['User']['Uris']['Node']['Uri']

    sync_directory_node(session, output_dir, root_node_endpoint)


if __name__ == '__main__':
    main()
