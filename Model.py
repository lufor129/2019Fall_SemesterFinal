from flask import Flask,request,abort,jsonify
import re
import pymongo
import json
import jieba
import pandas as pd
from gensim import corpora,models,similarities
import numpy as np
import random
import keras
import pickle
from keras.models import load_model

jieba.set_dictionary("./dict.txt.big.txt")


app = Flask(__name__)

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["semester"]
mycol = mydb["ettoday"]

print("load tfidf_model")
corpora_dict_path = './model/corpora_dict.dict'
tfidf_model_path = "./model/tfidf.model"
index_path = "./model/simIndex.index"
lsi_model_path = "./model/lsi_model.lsi"

tfidf = models.TfidfModel.load(tfidf_model_path)
dictionary = corpora.Dictionary.load(corpora_dict_path)
index = similarities.SparseMatrixSimilarity.load(index_path)
lsi =  models.LsiModel.load(lsi_model_path)

print("load LSTM")
model = load_model("./model/LSTM_model3.h5")
model._make_predict_function()

with open("./model/tokenized2.pickle","rb") as handle:
    tokenizer = pickle.load(handle)

print("load news data")
all_ettoday = []
for i in mycol.find({},{"_id":0}):
    all_ettoday.append(i)

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

def getLSI(text):
  texts = jieba.cut(text)
  new_vec = dictionary.doc2bow(texts)
  new_vec_tfidf = tfidf[new_vec]
  new_vec_lsi = lsi[new_vec_tfidf]
  return index[new_vec_lsi]


label_2_num = {
    0: 0,
    1: 0.7,
    2: -1
}
label_2_tag = {
    0:"unrelated",
    1:"agreed",
    2:"disagreed"
}

@app.route('/sentSims',methods=["POST"])
def sentSims():
  text = request.get_json(force=True)
  print(text)
  sims = getLSI(text)
  sims = sorted(enumerate(sims), key=lambda item: -item[1])
  result = [all_ettoday[sim[0]] for sim in sims[:20]]
  return jsonify(result)

@app.route("/Recomm",methods=["POST"])
def Recomm():
  favorite = request.get_json(force=True)
  sims = [getLSI(f) for f in favorite]
  sims = [sorted(enumerate(sim), key=lambda item: -item[1])[:20] for sim in sims]
  simAndimg = [[{"imgUrl":all_ettoday[s[0]],"sim":s[1]} for index,s in enumerate(sim) if s[1]>0.3 and index!=0] for sim in sims]
  mother = 0.
  for i in range(len(simAndimg)):
    mother += (i+1)

  result = []
  for index,r in enumerate(simAndimg):
    for k in r:
      if(random.random()<1.2*((index+1)/mother)*float(k["sim"])):
        k["sim"] = str(k["sim"])
        result.append(k)

  return jsonify(result)

@app.route("/FakeNewsJ",methods=['POST'])
def FakeNewsJ():
    top_sims_num = 10
    user_message = request.get_json(force=True)
    print(user_message)
    sims = getLSI(user_message)
    sims = sorted(enumerate(sims), key=lambda item: -item[1])
    input_data = [all_ettoday[sim[0]]["title"] for sim in sims[:top_sims_num]]

    display_news = [all_ettoday[sim[0]] for sim in sims[:top_sims_num]]

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
    lsi_sims = [str(sim[1]) for sim in sims[:top_sims_num]]
    pred_label = [str(label_2_tag[idx]) for idx in np.argmax(predictions, axis=1)]
    #pred_sent = [label_2_sent[idx] for idx in np.argmax(predictions, axis=1)]
    max_prediction_score = predictions[range(10),np.argmax(predictions, axis=1)]

    for index,score in enumerate(max_prediction_score):
        if((pred_label[index]=="agreed" and score <0.5) or float(lsi_sims[index])<0.7):
            max_prediction_score[index] = predictions[index,0]
            pred_label[index] = "unrelated"
    max_prediction_score = [str(pred) for pred in max_prediction_score]

    return jsonify({"lsi":lsi_sims,"label":pred_label,"pred_score":max_prediction_score,"data":display_news})


if __name__ == "__main__":
  app.run(port=3500)