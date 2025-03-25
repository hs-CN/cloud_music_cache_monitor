import os
import time
import filetype
import logging
import hashlib
import requests
from mutagen import id3, mp4

CACHE_PATH = r"C:\Users\hs199\AppData\Local\NetEase\CloudMusic\Cache\Cache"
MUSIC_DIR = "Music"
HISTORY_FILE = os.path.join(MUSIC_DIR, "history.txt")

logging.basicConfig(
    level=logging.INFO, format="[%(levelname)s][%(asctime)s] %(message)s"
)

if not os.path.exists(MUSIC_DIR):
    os.makedirs(MUSIC_DIR)


def convert_uc_to_music(uc_file_path):
    with open(uc_file_path, "rb") as f:
        data = f.read()
    arr = bytearray(data)

    for i in range(0, len(arr)):
        arr[i] = arr[i] ^ 0xA3

    uc_file_name = os.path.basename(uc_file_path)
    md5 = uc_file_name.rsplit("-", 1)[1][:-3]
    if md5 != hashlib.md5(arr).hexdigest():
        logging.info(f"Waitting cache [{uc_file_name}] ...")
        return None

    kind = filetype.guess(arr)
    if kind is None:
        file_path = os.path.join(MUSIC_DIR, uc_file_name[:-2] + "unknown")
        logging.warning(f"Cannot guess [{file_path}] file type!")
    else:
        file_path = os.path.join(MUSIC_DIR, uc_file_name[:-2] + kind.extension)

    with open(file_path, "wb") as f:
        f.write(arr)

    logging.info(f"Convert [{uc_file_name}] to [{kind.extension}]")
    return file_path


def get_music_info(file_path):
    file_name = os.path.basename(file_path)
    id = file_name.split("-")[0]
    url = f"http://music.163.com/api/song/detail/?id={id}&ids=[{id}]"
    response = requests.get(url)
    if response.status_code != 200:
        logging.warning(f"Failed to get music info for {file_name}")
        return
    music_detail = response.json()
    if music_detail["code"] != 200:
        logging.warning(f"Failed to get music info for {file_name}. {response.content}")
        return

    music_name = music_detail["songs"][0]["name"]
    music_artists = [artist["name"] for artist in music_detail["songs"][0]["artists"]]
    music_artists = " & ".join(music_artists)
    music_album = music_detail["songs"][0]["album"]["name"]

    # Add music info to file
    if file_name.endswith(".mp3"):
        audio = id3.ID3(file_path)
        audio.add(id3.TIT2(encoding=3, text=music_name))
        audio.add(id3.TPE1(encoding=3, text=music_artists))
        audio.add(id3.TALB(encoding=3, text=music_album))
        audio.save()
    elif file_name.endswith(".m4a"):
        audio = mp4.MP4(file_path)
        audio["\xa9nam"] = music_name
        audio["\xa9ART"] = music_artists
        audio["\xa9alb"] = music_album
        audio.save()
    elif file_name.endswith(".mp4"):
        audio = mp4.MP4(file_path)
        audio["\xa9nam"] = music_name
        audio["\xa9ART"] = music_artists
        audio["\xa9alb"] = music_album
        audio.save()
    else:
        logging.warning(f"Unsupported file format: {file_name}")

    # Add music album pic to file
    music_album_pic = music_detail["songs"][0]["album"]["picUrl"]
    if music_album_pic is not None and music_album_pic != "":
        response = requests.get(music_album_pic)
        if response.status_code == 200:
            pic_bytes = response.content
            if file_name.endswith(".mp3"):
                audio = id3.ID3(file_path)
                audio.add(id3.APIC(3, "image/jpeg", 3, "Front cover", pic_bytes))
                audio.save()
            elif file_name.endswith(".m4a"):
                audio = mp4.MP4(file_path)
                audio["covr"] = [
                    mp4.MP4Cover(pic_bytes, imageformat=mp4.MP4Cover.FORMAT_JPEG)
                ]
                audio.save()
            elif file_name.endswith(".mp4"):
                audio = mp4.MP4(file_path)
                audio["covr"] = [
                    mp4.MP4Cover(pic_bytes, imageformat=mp4.MP4Cover.FORMAT_JPEG)
                ]
                audio.save()

    file_ext = os.path.splitext(file_path)[1]
    new_file_name = f"{music_name} - {music_artists}{file_ext}"
    new_file = os.path.join(MUSIC_DIR, new_file_name)
    os.rename(file_path, new_file)
    logging.info(f"Rename to [{new_file_name}]")
    return new_file


def load_history():
    history = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                history.add(line.strip())
    return history


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        for item in history:
            f.write(item + "\n")


logging.info(f"Start monitoring {CACHE_PATH} ...")
history = load_history()
while True:
    try:
        uc_files = [file for file in os.listdir(CACHE_PATH) if file.endswith(".uc")]
        for uc_file_name in uc_files:
            if uc_file_name in history:
                continue
            uc_file_path = os.path.join(CACHE_PATH, uc_file_name)
            music_file_path = convert_uc_to_music(uc_file_path)
            if music_file_path is None:
                continue
            get_music_info(music_file_path)
            history.add(uc_file_name)
            save_history(history)
        time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Exit...")
        break
