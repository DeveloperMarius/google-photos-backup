# Backup script for Google Photos

Synology does not have an option to backup Google Photos. This script downloads all Google Photos.  
It will not delete files when they are deleted in the cloud. 

## Setup Google Cloud
Create a Google Cloud App and add the Google Photos Library.  
Add oAuth2 credentials for a webapp and add a custom redirect uri (https://developers.google.com/oauthplayground tokens will be revoked after 7 days).

Detailed: https://stackoverflow.com/questions/19766912/how-do-i-authorise-an-app-web-or-installed-without-user-intervention/19766913#19766913  
Permissions: https://developers.google.com/photos/library/guides/authorization?hl=de

## Run the script

### Configure
`cp example.env .env`

### Receive code

`python3 main.py -g`

### Exchange code for refresh token

`python3 main.py -f <code>`

### Run
`python3 main.py /temp`
