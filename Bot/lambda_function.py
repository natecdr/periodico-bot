import os
from pathlib import Path
import tweepy
import pandas as pd
import re
import unidecode
import imageio as iio
import numpy as np 
import boto3

ROOT = Path(__file__).resolve().parents[0]

def starts_with(string, start):
    return bool(re.match(start, string, re.I))

def encrypt(original_in):
    periodic_data = pd.read_csv(ROOT/"periodic.csv")
    symbols = periodic_data["Symbol"].to_numpy()
    symbols = [symbol.strip() for symbol in symbols]

    unidecoded_in = unidecode.unidecode(original_in)
    original_in = unidecoded_in if len(unidecoded_in) == len(original_in) else original_in
    res = encrypt_r(original_in, original_in, [], symbols)
    print("Debug:", original_in)
    return res if len("".join(res)) == len(original_in) else None

def encrypt_r(original_in, remainder, res, symbols):
    if len(remainder) == 0:
        return res
    else:
        if not remainder[0].isalpha():
            new_remainder = remainder[1:]
            res = encrypt_r(original_in, new_remainder, res+[remainder[0]], symbols)
        else:
            res_temp = res
            for symbol in symbols:
                if starts_with(remainder, symbol):
                    new_remainder = remainder[len(symbol):]
                    res = encrypt_r(original_in, new_remainder, res_temp+[symbol], symbols)
                    if "".join(res).lower() == original_in.lower():
                        break

    return res

def get_words_from_file(filename):
    f = open(ROOT/filename, "r")
    content = f.read()
    return content.split("\n")[:-1]

def read_index_file(path):
    client = boto3.client("ssm")
    param = int(client.get_parameter(Name="periodico-index")["Parameter"]["Value"])
    return param

def update_index(new_index):
    client = boto3.client("ssm")
    param = client.get_parameter(Name="periodico-index")
    client.put_parameter(Name="periodico-index", Value=str(new_index), Type="String", Overwrite=True)

def get_next_word_encrypted():
    words = get_words_from_file("words.txt")
    i = int(read_index_file("/tmp/word_index.txt"))

    print("Crypting word...")
    encrypted_word = None
    while encrypted_word is None and i < len(words):
        encrypted_word = encrypt(words[i])
        i += 1
    print("Done.")
    
    update_index(i)

    return encrypted_word

def crypt_to_image(crypt):
    ims = []
    for symbol in crypt:
        if not symbol.isspace():
            im = iio.imread(str(ROOT)+"/IMG/"+symbol+".png") 
            im[im==0] = 255
            ims.append(im)
        else: 
            ims.append(np.full((512,256,3),255))
            
    res = np.concatenate(ims, axis=1)
    return res

def post_next_tweet(api):
    try:
        print("Getting next word...")
        next_word = get_next_word_encrypted() 
        print("Done")
        iio.imwrite("/tmp/res.png", crypt_to_image(next_word))
        response = api.update_status("".join(next_word))
        api.update_status_with_media(status = "", filename= "/tmp/res.png", in_reply_to_status_id = response.id , auto_populate_reply_metadata=True)
    except Exception as e:
        print("MAMA:", str(e))
        post_next_tweet(api)

def lambda_handler(event, context):
    print("Getting credentials...")
    consumer_key = os.getenv("CONSUMER_KEY")
    consumer_secret = os.getenv("CONSUMER_SECRET")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    print("Authenticating...")
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret, access_token, access_token_secret)
    api = tweepy.API(auth)
    post_next_tweet(api)
    
    return {"statusCode": 200}
