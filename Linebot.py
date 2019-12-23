from flask import Flask, request, abort
import jieba
import re
import pymongo
from gensim import corpora,models,similarities
import pandas as pd
from keras.models import load_model
import keras
import pickle
import os
import numpy as np
import random

jieba.set_dictionary("dict.txt.big.txt")

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["semester"]
mycol = mydb["ettoday"]

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

app = Flask(__name__)

line_bot_api = LineBotApi('V2k38s3HtXrB/IEeF8gLc3D4f1PBWQNTG5J56o8o6k8nQtyinHgAeP/MeM+CV21Xci+bOK42y6qseg99STmf+bPBXdecFH7bgjyJz06PMeowGAyfzAtYheAnpoNGbzWqfMU4NnzLKm/Df9Jr88V2FwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('39a9319aa7d756a5f76e27fd22ecda7c')

print("load tfidf_model")
corpora_dict_path = './model/corpora_dict.dict'
tfidf_model_path = "./model/tfidf.model"
index_path = "./model/simIndex.index"
lsi_model_path = "./model/lsi_model.lsi"

tfidf = models.TfidfModel.load(tfidf_model_path)
dictionary = corpora.Dictionary.load(corpora_dict_path)
index = similarities.SparseMatrixSimilarity.load(index_path)
lsi =  models.LsiModel.load(lsi_model_path)

model = load_model("./model/LSTM_model3.h5")
model._make_predict_function()

with open("./model/tokenized2.pickle","rb") as handle:
    tokenizer = pickle.load(handle)

def cleanData(sentence):
    sentence = re.sub("快訊","",sentence)
    sentence = re.sub("\W+","",sentence)
    texts = jieba.cut(sentence)
    arr = []
    for t in texts:
        if(t.isdigit() or re.search("[^a-zA-Z]+",t) == None):
            arr.append(t)
            continue
        else:
            for tee in t:
                arr.append(tee)
    return " ".join(arr)

def stringify(text):
    return str(text)

print("load news data")
all_ettoday = []
for i in mycol.find({},{"title":1}):
    all_ettoday.append(i)

def getSims(sentence):
    texts = jieba.cut(sentence)
    new_vec = dictionary.doc2bow(texts)
    new_vec_tfidf = tfidf[new_vec]
    new_vec_lsi = lsi[new_vec_tfidf]
    return index[new_vec_lsi]
label_2_num = {
    0: 0,
    1: 0.7,
    2: -1
}

label_2_sent = {
    0: "兩句話不相關",
    1: "此新聞贊同",
    2: "此新聞不贊同"
}

def judgeScore(score):
    if(score<3):
        return "我們猜應該是假新聞"
    elif(score<5 and score >=3):
        return "我們認為可能新聞不在新聞資料庫內，或是有爭議無法評定"
    else:
        return "我們認為是真新聞"

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    top_sims_num = 10
    user_message = event.message.text
    sims = getSims(user_message)
    sims = sorted(enumerate(sims), key=lambda item: -item[1])
    input_data = [all_ettoday[sim[0]]["title"] for sim in sims[:top_sims_num]]

    display_news = []
    input_id = [all_ettoday[sim[0]]["_id"] for sim in sims[:top_sims_num]]
    for i in input_id:
        display_news.append(mycol.find_one({"_id":i}))

    input_data = pd.DataFrame(input_data)
    input_data.columns = ["title2"]
    input_data["title1"] = user_message
    MAX_SEQUENCE_LENGTH = 25
    input_data['title1_tokenized'] = \
        input_data.loc[:, 'title1'].apply(stringify).apply(cleanData)
    input_data['title2_tokenized'] = \
        input_data.loc[:, 'title2'].apply(stringify).apply(cleanData)

    x1_test = tokenizer \
        .texts_to_sequences(
             input_data.title1_tokenized)
    x2_test = tokenizer \
        .texts_to_sequences(
             input_data.title2_tokenized)

    x1_test = keras \
        .preprocessing \
        .sequence \
        .pad_sequences(
            x1_test,
            maxlen=MAX_SEQUENCE_LENGTH)
    x2_test = keras \
        .preprocessing \
        .sequence \
        .pad_sequences(
            x2_test,
            maxlen=MAX_SEQUENCE_LENGTH)
    predictions = model.predict([x1_test, x2_test])
    #input_data['Category'] = [index_to_label[idx] for idx in np.argmax(predictions, axis=1)]
    #lsi_index = [sim[0] for sim in sims[:top_sims_num]]
    lsi_sims = [sim[1] for sim in sims[:top_sims_num]]
    pred_label = [label_2_num[idx] for idx in np.argmax(predictions, axis=1)]
    pred_sent = [label_2_sent[idx] for idx in np.argmax(predictions, axis=1)]

    score = 0.

    for i in range(len(lsi_sims)):
        score += lsi_sims[i]*pred_label[i]

    max_prediction_score = predictions[range(10),np.argmax(predictions, axis=1)]

    columns = []
    for i in range(10):
        columns.append(
            CarouselColumn(
                thumbnail_image_url= "https://lufor129.nctu.me/images/"+re.sub("./pic/","",display_news[i]["img_path"]),
                title=display_news[i]["title"][:40],
                text= "你的輸入與新聞相似度: "+str(round(lsi_sims[i],2))+"\n"+pred_sent[i]+"的機率是: "+str(round(max_prediction_score[i],2)),
                actions=[
                    URITemplateAction(
                        label='新聞連結',
                        uri=display_news[i]["link"]
                    )
                ]
            )
        )
    Carousel_template = TemplateSendMessage(
        alt_text='Carousel template',
        template=CarouselTemplate(
            columns = columns
        )
    )

    text_message = TextSendMessage(
        text = "經過嚴密計算:\n"+judgeScore(score)+"\n"+str(score)
    )
    line_bot_api.reply_message(
        event.reply_token,
        #TextSendMessage(text=str(score)
        [Carousel_template,text_message]
    )
    return 0

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker_message(event):
    sticker_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 100, 101, 102, 103, 104, 105, 106,
                   107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125,
                   126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 401, 402]
    index_id = random.randint(0, len(sticker_ids) - 1)
    sticker_id = str(sticker_ids[index_id])
    sticker_message = StickerSendMessage(
        package_id='1',
        sticker_id=sticker_id
    )
    line_bot_api.reply_message(
        event.reply_token,
        sticker_message)
    return 0

if __name__ == "__main__":
    app.run()