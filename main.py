import json
import time
import requests
import os
import threading
import argparse
import pathlib


class Config:

    @staticmethod
    def read():
        with open(f"{pathlib.Path(__file__).parent.resolve()}/.env", 'r') as file:
            for line in file.readlines():
                if '=' in line:
                    split = line.replace("\n", "").replace("\r", "").split("=", 2)
                    os.environ[split[0]] = split[1]

    @staticmethod
    def get_scope():
        return 'https://www.googleapis.com/auth/photoslibrary.readonly'

    @staticmethod
    def get_base_url():
        return 'https://photoslibrary.googleapis.com'

    @staticmethod
    def get_client_id():
        return os.getenv('GOOGLE_CLIENT_ID')

    @staticmethod
    def get_client_secret():
        return os.getenv('GOOGLE_CLIENT_SECRET')

    @staticmethod
    def get_client_refresh_token():
        return os.getenv('GOOGLE_CLIENT_REFRESH_TOKEN')

    @staticmethod
    def get_client_redirect_uri():
        return os.getenv('GOOGLE_CLIENT_REDIRECT_URI')


class GoogleClient:

    def __init__(self):
        self.access_token = None
        self.access_token_expires = None

    def fetch_refresh_token(self, code):
        response = requests.request('POST', 'https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': Config.get_client_id(),
            'client_secret': Config.get_client_secret(),
            'grant_type': 'authorization_code',
            'scope': Config.get_scope(),
            'redirect_uri': Config.get_client_redirect_uri()
        })
        data = json.loads(response.content)
        print(data)
        if 'error' in data:
            raise Exception(f"{data['error']}: {data['error_description']}")

    def fetch_access_token(self):
        print(f"Fetching new access token...")
        response = requests.request('POST', 'https://oauth2.googleapis.com/token', data={
            'refresh_token': Config.get_client_refresh_token(),
            'client_id': Config.get_client_id(),
            'client_secret': Config.get_client_secret(),
            'grant_type': 'refresh_token'
        })
        data = json.loads(response.content)
        if 'error' in data:
            raise Exception(f"{data['error']}: {data['error_description']}")
        self.access_token = data['access_token']
        self.access_token_expires = round(time.time()) + data['expires_in'] - 10

    def get_access_token(self):
        if self.access_token is None or (self.access_token_expires is not None and self.access_token_expires <= round(time.time())):
            self.fetch_access_token()
        return self.access_token

    def request(self, method, uri, params=None):
        response = requests.request(method, Config.get_base_url() + uri, headers={
            'Authorization': f"Bearer {self.get_access_token()}"
        }, params=params)
        data = json.loads(response.content)
        return data


class MediaItemListResponse:

    def __init__(self, data):
        self.next_page_token = data['nextPageToken'] if 'nextPageToken' in data else None
        self.media_items = []
        if 'mediaItems' in data:
            for media_item in data['mediaItems']:
                self.media_items.append(MediaItem(media_item))


class MediaItem:

    def __init__(self, data):
        self.id = data['id'] if 'id' in data else None
        self.product_url = data['productUrl'] if 'productUrl' in data else None
        self.base_url = data['baseUrl'] if 'baseUrl' in data else None
        self.mime_type = data['mimeType'] if 'mimeType' in data else None
        self.media_metadata = MediaItemMetadata(data['mediaMetadata']) if 'mediaMetadata' in data else None
        self.filename = data['filename'] if 'filename' in data else None

    def get_extension(self):
        return self.mime_type.split('/')[1]

    def file_exists(self, filename):
        return os.path.isfile(filename)

    def get_local_filename(self, directory):
        return f"{directory}/{self.media_metadata.creation_time.replace(':','-')}-{self.id}.{self.get_extension()}"

    def save_to(self, directory, force_update=False):
        if not force_update and self.file_exists(self.get_local_filename(directory)):
            raise MediaItemAlreadyDownloadedException(self, 'File already downloaded')
        if self.mime_type.startswith('image/'):
            response = requests.get(f"{self.base_url}=d")
        elif self.mime_type.startswith('video/'):
            response = requests.get(f"{self.base_url}=dv")
        else:
            raise Exception('Media Type not supported')
        with open(self.get_local_filename(directory), 'wb') as file:
            file.write(response.content)


class MediaItemAlreadyDownloadedException(Exception):

    def __init__(self, media_item, message="This Media Item is already downloaded"):
        self.media_item = media_item
        self.message = f"The Media Item {self.media_item.id}  is already downloaded"
        super().__init__(self.message)


class MediaItemMetadata:

    def __init__(self, data):
        self.creation_time = data['creationTime'] if 'creationTime' in data else None
        self.width = data['width'] if 'width' in data else None
        self.height = data['height'] if 'height' in data else None
        self.photo = MediaItemMetadataPhoto(data['photo']) if 'photo' in data and len(data['photo']) > 0 else None
        self.video = MediaItemMetadataPhoto(data['video']) if 'video' in data and len(data['video']) > 0 else None


class MediaItemMetadataPhoto:

    def __init__(self, data):
        self.camera_make = data['cameraMake'] if 'cameraMake' in data else None
        self.camera_model = data['cameraModel'] if 'cameraModel' in data else None
        self.focal_length = data['focalLength'] if 'focalLength' in data else None
        self.aperture_f_number = data['apertureFNumber'] if 'apertureFNumber' in data else None
        self.iso_equivalent = data['isoEquivalent'] if 'isoEquivalent' in data else None
        self.exposure_time = data['exposureTime'] if 'exposureTime' in data else None


class MediaItemMetadataVideo:

    def __init__(self, data):
        self.camera_make = data['cameraMake'] if 'cameraMake' in data else None
        self.camera_model = data['cameraModel'] if 'cameraModel' in data else None
        self.fps = data['fps'] if 'fps' in data else None
        self.status = data['status'] if 'status' in data else None


class MediaItemService:

    def __init__(self, client):
        self.client = client

    def list(self, page_size=100, page_token=None):
        data = self.client.request('GET', '/v1/mediaItems', params={
            'pageSize': page_size,
            'pageToken': page_token
        })
        return MediaItemListResponse(data)

    def download_all(self, directory, force_update=False):
        next_page = None
        first = True
        while next_page is not None or first:
            print(f"Downloading page: {next_page if next_page is not None else 'N/A'}")
            first = False
            try:
                response = self.list(page_token=next_page)
                next_page = response.next_page_token
                for item in response.media_items:
                    try:
                        item.save_to(directory, force_update)
                    except MediaItemAlreadyDownloadedException as e:
                        print(f"MediaItem {item.id} already downloaded.")
                        next_page = None
                        break
                    except Exception as e:
                        print(f"MediaItem {item.id}: ", e)
            except Exception as e:
                print(e)
                break


# Is not giving more performance because network is the problem
class MediaItemDownloader:

    def __init__(self, media_items, directory, force_update):
        self.media_items = media_items
        self.directory = directory
        self.force_update = force_update

    def start(self):
        # creating a lock
        lock = threading.Lock()

        # creating threads
        t1 = threading.Thread(target=self.start_thread_task, args=(lock,))
        t2 = threading.Thread(target=self.start_thread_task, args=(lock,))
        t3 = threading.Thread(target=self.start_thread_task, args=(lock,))

        # start threads
        t1.start()
        t2.start()
        t3.start()

        # wait until threads finish their job
        t1.join()
        t2.join()
        t3.join()

    def start_thread_task(self, lock):
        while True:
            lock.acquire()
            if len(self.media_items) == 0:
                break
            media_item = self.media_items.pop()
            lock.release()
            try:
                media_item.save_to(self.directory, self.force_update)
            except KeyError as e:
                print(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Google Photos Backup', description='Backup Google Photos to disc')
    parser.add_argument('output_dir', nargs='?', default=os.getcwd())
    parser.add_argument('-f', '--fetch_refresh_token', dest='code', nargs=1)
    parser.add_argument('-g', '--generate_uri', dest='generate_uri', action='store_true')
    args = parser.parse_args()

    Config.read()
    client = GoogleClient()
    if args.generate_uri:
        print(f"URI: https://accounts.google.com/o/oauth2/v2/auth?redirect_uri={Config.get_client_redirect_uri()}&prompt=consent&response_type=code&client_id={Config.get_client_id()}&scope={Config.get_scope()}&access_type=offline")
    elif args.code is not None and len(args.code) == 1:
        client.fetch_refresh_token(args.code[0])
    else:
        service = MediaItemService(client)
        print(f"Starting downloading...")
        service.download_all(args.output_dir)
        print(f"Finished downloading.")
