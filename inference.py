from transformers import AutoTokenizer, AutoConfig, AutoModelForSequenceClassification, Trainer, TrainingArguments
from torch.utils.data import DataLoader
from semantic_load_data import *
import pandas as pd
import torch
import torch.nn.functional as F

import pickle as pickle
import numpy as np
import argparse
from tqdm import tqdm

from train import set_seed

from sklearn.metrics import f1_score

def inference(model, tokenized_sent, device, tokenizer):
  """
    test dataset을 DataLoader로 만들어 준 후,
    batch_size로 나눠 model이 예측 합니다.
  """
  dataloader = DataLoader(tokenized_sent, batch_size=16, shuffle=False)
  # print("input_ids : " ,tokenizer.decode(tokenized_sent[1]['input_ids']))
  model.eval()
  output_pred = []
  output_prob = []
        
  for i, data in enumerate(tqdm(dataloader)):
    with torch.no_grad():
      outputs = model(
          input_ids=data['input_ids'].to(device),
          attention_mask=data['attention_mask'].to(device),
          token_type_ids=data['token_type_ids'].to(device)
          )
    logits = outputs[0]
    prob = F.softmax(logits, dim=-1).detach().cpu().numpy()
    logits = logits.detach().cpu().numpy()
    result = np.argmax(logits, axis=-1)

    output_pred.append(result)
    output_prob.append(prob)
  
  return np.concatenate(output_pred).tolist(), np.concatenate(output_prob, axis=0).tolist()

def num_to_label(label):
  """
    숫자로 되어 있던 class를 원본 문자열 라벨로 변환 합니다.
  """
  origin_label = []
  with open('./utils/dict_num_to_label.pkl', 'rb') as f:
    dict_num_to_label = pickle.load(f)
  for v in label:
    origin_label.append(dict_num_to_label[v])
  
  return origin_label

def load_test_dataset(dataset_dir, tokenizer):
  """
    test dataset을 불러온 후,
    tokenizing 합니다.
  """
  test_dataset, sp_token_list, semantic_sentence  = load_data(dataset_dir, args.preprocessing_mode, args.preprocessing_mode, args.sentence_mode)   #######################
  print("test_dataset.head(3)==================")
  print(test_dataset.head(3))
  test_label = list(map(int,test_dataset['label'].values))
  if sp_token_list is not None :
    tokenizer.add_special_tokens({'additional_special_tokens':sp_token_list}) 
  # tokenizing dataset
  tokenized_test = tokenized_dataset(test_dataset, tokenizer, semantic_sentence)
  return test_dataset['id'], tokenized_test, test_label, sp_token_list

def main(args):
  set_seed(42)
  """
    주어진 dataset csv 파일과 같은 형태일 경우 inference 가능한 코드입니다.
  """
  device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
  # load tokenizer
  Tokenizer_NAME = args.model_name
  tokenizer = AutoTokenizer.from_pretrained(Tokenizer_NAME)

  ## load my model
  MODEL_NAME = args.model_dir # model dir.
  model = AutoModelForSequenceClassification.from_pretrained(args.model_dir)
  model.parameters
  model.to(device)
  
  ## load test datset
  test_dataset_dir = args.test_dataset_dir
  
  test_id, test_dataset, test_label, sp_token_list = load_test_dataset(test_dataset_dir, tokenizer)
  Re_test_dataset = RE_Dataset(test_dataset ,test_label)
  model.resize_token_embeddings(len(tokenizer))
  
  ## predict answer
  pred_answer, output_prob = inference(model, Re_test_dataset, device, tokenizer) # model에서 class 추론
  pred_answer = num_to_label(pred_answer) # 숫자로 된 class를 원래 문자열 라벨로 변환.
  
  ## make csv file with predicted answer
  #########################################################
  # 아래 directory와 columns의 형태는 지켜주시기 바랍니다.
  output = pd.DataFrame({'id':test_id,'pred_label':pred_answer,'probs':output_prob,})
  
  output.to_csv(args.output_dir, index=False) # 최종적으로 완성된 예측한 라벨 csv 파일 형태로 저장.
  #### 필수!! ##############################################
  print('---- Finish! ----')
  

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  # model dir
  parser.add_argument('--test_dataset_dir', type=str, default="../dataset/test/test_data.csv")
  parser.add_argument('--output_dir', type=str, default="./prediction/submission.csv")
  
  parser.add_argument('--model_dir', type=str, default="./best_model/best_model-sweep-fold2-2024_01_17_15_32_38}")
  parser.add_argument('--model_name', type=str, default="klue/roberta-large")    
  parser.add_argument('--preprocessing_mode', type=str, default="punct_eng")
  parser.add_argument('--sentence_mode', type=str, default="1")
  args = parser.parse_args()
  
  main(args)
  
  