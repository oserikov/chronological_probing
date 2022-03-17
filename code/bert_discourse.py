from transformers import BertTokenizer, BertModel
import torch
from tqdm import tqdm
import pickle
import numpy as np

device = 'cuda:0'


class Embeddings(object):
    def __init__(self, path, sentences, checkpoints, size, emb_name, delay=0):
        self.path = path
        self.sentences = sentences
        self.checkpoints = checkpoints
        self.size = size
        self.emb_name = emb_name
        self.delay = delay
    
    def load_model(self, checkpoint_path):
        """
        Loads a transformer model
        :return: a model and a tokenizer
        """
        #m = torch.load(checkpoint_path)
        #model = T5ForConditionalGeneration(T5Config(output_hidden_states=True))
        #model.load_state_dict(m['model_state_dict'])
        model = BertModel.from_pretrained(checkpoint_path, output_hidden_states=True)
        model.to(device)
        return model

    def encode(self, tokenizer):
        batches = []
        for text in self.sentences:
              tokenized_text = tokenizer.batch_encode_plus(text,
                                                  max_length=512,
                                                  add_special_tokens=True,
                                                  padding=True,
                                                  truncation=True,
                                                  return_attention_mask=True)
              batches.append(tokenized_text)
        return batches

    def mean_pooling(self, model_output, attention_mask, emb_number):
        final_tokens = np.zeros((model_output[0].shape[0], self.size, 13))
        tokens = model_output[0].cpu().detach().numpy()
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(tokens.shape).float().cpu().detach().numpy() 
        normalized = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)
        for num, i in enumerate(model_output):
            tokens = i.cpu().detach().numpy() # batch_size x seq_len x emb_size
            final_tokens[:,:,num] = np.sum(tokens * input_mask_expanded, axis=1)/normalized
        return final_tokens

    def get_emb(self, batch, model, emb_number):
        """
        Encodes a sentence and returns an embedding
        :param batch: a batch
        :param model: a transformer model
        :return:
        """
        input_ids = torch.tensor(batch['input_ids'], dtype=torch.long).to(device)
        attention_mask = torch.tensor(batch['attention_mask'], dtype=torch.long).to(device)
        with torch.no_grad():
            output = model(
              input_ids=input_ids,
              attention_mask=attention_mask,
              return_dict=True
            )
        emb = output.hidden_states
        mean_pool = self.mean_pooling(emb, attention_mask, emb_number)
        embedding = np.concatenate(mean_pool, axis=0) 
        return embedding

    def calculate_embeddings(self, path, tokenizer):
        """
        Calculates embeddings for all sentences
        :param path: a path to a checkpoint
        :param sentences: a corpus of texts
        :return: a matrix of embeddings
        """
        labels = []
        model = self.load_model(path)
        print('Model is loaded')
        batches = self.encode(tokenizer)
        emb_number = len(batches[0]['input_ids'])
        embeddings = np.zeros((len(self.sentences), self.size * emb_number, 13))
        for i, batch in enumerate(batches):
            embeddings[i] = self.get_emb(batch, model, emb_number)
        print('Embeddings are calculated')
        return embeddings

    def save_embeddings(self, embeddings, checkpoint):
        """
        Saves embeddings to a pickle file
        :param embeddings: a matrix of embeddings
        :param checkpoint: a checkpoint
        :return: a pickle file
        """
        with open(f'embeddings/BERT_checkpoints_{self.emb_name}_{checkpoint+self.delay}.pickle', 'wb') as f:
            pickle.dump(embeddings, f, protocol=4)

    def calculate(self):
        tokenizer = BertTokenizer.from_pretrained("google/multiberts-seed_0")
        for checkpoint in tqdm(range(self.checkpoints)):
            path = self.path[checkpoint]
            embs = self.calculate_embeddings(path, tokenizer)
            self.save_embeddings(embs, checkpoint)