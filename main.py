import json
import requests
import subprocess

from time import sleep
from typing import Any, Dict, Optional, Tuple
from os import environ

from report import create_report_md, REPORT_DIR


QUERY_FILE = 'overpass_query.txt'
BACKUP_FILE = 'aed_overpass.json'
README_FILE = 'README.MD'


BACKUP_COMMIT_MSG = 'AED update'

OVERPASS_API_URL = 'https://lz4.overpass-api.de/api/interpreter'

TIMEOUT = 30  # seconds
RETRIES = 5


def git_add(filename: str) -> None:
    subprocess.run(['git', 'add', filename])


def git_commit(msg: str) -> None:
    subprocess.run(['git', 'commit', '-m', f'{msg}'])
    print(msg)


def git_push() -> None:
    subprocess.run(['git', 'push'])


def download_data() -> Optional[Dict[Any, Any]]:
    with open(QUERY_FILE, 'r') as f:
        query = f.read().strip()

    for _ in range(RETRIES):
        try:
            response = requests.get(OVERPASS_API_URL, params={'data': query})
            if response.status_code != 200:
                print(f'Incorrect status code: {response.status_code}')
                continue

            return response.json()

        except Exception as e:
            print(f'Error with downloading/parsing data: {e}')

        sleep(TIMEOUT)


def backup(overpass_result: Dict[Any, Any]) -> None:
    with open(BACKUP_FILE, 'w') as f:
        json.dump(overpass_result, f, indent=4, ensure_ascii=False)

    git_add(BACKUP_FILE)


def generate_report(overpass_result: Dict[Any, Any]) -> None:
    try:
        md_content = create_report_md(overpass_result)
        with open(README_FILE, 'w') as f:
            f.write(md_content)

        git_add(README_FILE)
        git_add(REPORT_DIR)

    except Exception as e:
        print(f'Error with creating report: {e}')


def overpass_diff(overpass_data: Dict[Any, Any]) -> Tuple[int, int, int]:
    """
    :return: tuple with 3 numbers (created, modified, deleted) objects
    """
    created = 0
    modified = 0
    deleted = 0

    try:
        with open(BACKUP_FILE, 'r') as f:
            old_data = json.load(f)

    except IOError:
        old_data = {'elements': []}

    old_elements = {elem['id']: elem for elem in old_data['elements']}
    for elem in overpass_data['elements']:
        elem_id = elem['id']

        if elem_id not in old_elements:
            created += 1
        else:
            if elem != old_elements[elem_id]:
                modified += 1

            del old_elements[elem_id]

    deleted += len(old_elements)

    return created, modified, deleted


def main():
    overpass_data = download_data()
    if overpass_data is None:
        exit(1)

    diff = overpass_diff(overpass_data)
    backup(overpass_data)

    if any(diff):
        generate_report(overpass_data)

    if environ.get('PROD', None) not in ('true', '1'):
        exit(0)

    git_commit('{} (C: {}, M: {}, D: {})'.format(BACKUP_COMMIT_MSG, *diff))
    git_push()


if __name__ == '__main__':
    main()
