import os, json, torch, os
import pandas as pd
import numpy as np
from tqdm.auto import tqdm
from flair.data import Sentence
from flair.embeddings import TransformerWordEmbeddings
from transformers import TransfoXLModel, TransfoXLTokenizer, XLNetModel, XLNetTokenizer, XLMModel, XLMTokenizer
from nltk import tokenize, word_tokenize
from gensim.models import FastText, Word2Vec
from pathlib import Path

class GeneralEncoder:
    '''An interface for interacting with the fasttext model'''
    def __init__(self, data_dir, data, embedding = None):
        # Prepare tqdm loops
        tqdm.pandas()

        # Save variables to class
        self.embedding = embedding
        self.data_dir = data_dir
        self.df = data

        print(len(self.df))
    
    def get_embedder(self):
        '''Empty script for setting custom embedder'''
        raise ValueError('This function should be implemented in the children encoders')
    
    def create_embedding(self, statement, embedder):
        '''Create a single embedding from a piece of text'''
        raise ValueError('This function should be implemented in the children encoders')
    
    def get_embedding_dir(self, embedding):
        '''Turn the name of the embedding technique into a specific folder'''
        if '/' in embedding:
            return embedding.split('/')[1]
        else:
            return embedding

    def get_embedded_dataset(self, save = True):
        '''Return the embedding representation of the dataset'''
        
        def encode_datasets(embedding_dir, data_dir, df, embedding):
            '''Return all datasets with embeddings instead of texts'''
            # Check whether there already is a file containing the embeddings
            if embedding_dir in os.listdir(data_dir):
                # Return the previously made embeddings
                return pd.read_pickle(os.path.join(
                    data_dir, embedding_dir, 'data.pkl'
                ))
            else:
                print('Creating representations and saving them as files...')

                embedder = self.get_embedder()

                # Apply transformation
                df['embedding'] = df['name'].progress_map(
                    lambda text: self.create_embedding(text, embedder)
                )

                print('Make sure this is okay:')
                print(df.iloc[0])

                if save:
                    if embedding_dir not in os.listdir(data_dir):
                        # Create a location to save the datasets as pickle files
                        os.mkdir(os.path.join(data_dir, embedding_dir))

                    # Save the dataset as pickle file
                    file_path = os.path.join(data_dir, embedding_dir, 'data.pkl')
                    df.to_pickle(file_path)
                    print('Saved data.pkl at ' + file_path)
                
                return df
        
        # Directory name for saving the datasets
        embedding_dir = self.get_embedding_dir(self.embedding)

        return encode_datasets(embedding_dir, self.data_dir, self.df, self.embedding)

class FlairEncoder(GeneralEncoder):
    '''An interface for interacting with Zalando's Flair library'''
    def get_embedder(self):
        # Activate embedding
        if self.embedding == 'transfo-xl-wt103':
            embedding = {
                'model': TransfoXLModel.from_pretrained('transfo-xl-wt103'),
                'tokenizer': TransfoXLTokenizer.from_pretrained('transfo-xl-wt103'),
            }
        elif self.embedding == 'xlm-mlm-en-2048':
            embedding = {
                'model': XLMModel.from_pretrained('transfo-xl-wt103'),
                'tokenizer': XLMTokenizer.from_pretrained('transfo-xl-wt103'),
            }
        elif self.embedding == 'xlnet-base-cased':
            embedding = {
                'model': XLNetModel.from_pretrained('transfo-xl-wt103'),
                'tokenizer': XLNetTokenizer.from_pretrained('transfo-xl-wt103'),
            }
        else:
            embedding = TransformerWordEmbeddings(self.embedding)
        
        return embedding
    
    def create_embedding(self, statement, embedder):
        '''Create a single embedding from a piece of text'''
        # Split all sentences
        sentences = tokenize.sent_tokenize(statement)

        # Create an array for storing the embeddings
        vector = []

        # Loop over all sentences and apply embedding
        for sentence in sentences:
            if isinstance(embedder, dict):
                # Get embedding from Huggingface directly
                input_ids = torch.tensor(embedder['tokenizer'].encode(sentence)).unsqueeze(0)
                outputs = embedder['model'](input_ids)
                last_hidden_states = outputs[0]
                vector.append(list(last_hidden_states[0].detach().numpy()))
            else:
                # Continue as "regular" Flair-based embedding
                # Create a Sentence object for each sentence in the statement
                sentence = Sentence(sentence, use_tokenizer = True)

                # Embed words in sentence
                embedder.embed(sentence)
                vector.append([token.embedding.cpu().numpy() for token in sentence])

        return vector

class FastTextEncoder(GeneralEncoder):
    '''An interface for interacting with fastText'''
    def get_embedding_dir(self, embedding):
        '''Turn the name of the embedding technique into a specific folder'''
        return 'fasttext'

    def get_embedder(self):
        # Activate embedding
        vocab = np.array([word_tokenize(sentence) for sentence in self.df['name'].to_list()], dtype=object).flatten()
        print(vocab[:25])

        embedding = FastText(vocab, min_count=1, size=400)
        
        return embedding
    
    def create_embedding(self, statement, embedder):
        '''Create a single embedding from a piece of text'''
        # Split all sentences
        sentences = tokenize.sent_tokenize(statement)

        # Create an array for storing the embeddings
        vector = [[embedder.wv.get_vector(token) for token in word_tokenize(sentence)] for sentence in sentences]

        return vector


class Word2VecEncoder(GeneralEncoder):
    '''An interface for interacting with word2vec'''
    def get_embedding_dir(self, embedding):
        '''Turn the name of the embedding technique into a specific folder'''
        return 'word2vec'

    def get_embedder(self):
        # Activate embedding
        vocab = [[x] for x in np.array([word_tokenize(sentence) for sentence in self.df['name'].to_list()]).flatten()]

        embedding = Word2Vec(vocab, min_count=1, size=400)
        
        return embedding
    
    def create_embedding(self, statement, embedder):
        '''Create a single embedding from a piece of text'''
        # Split all sentences
        sentences = tokenize.sent_tokenize(statement)

        # Create an array for storing the embeddings
        vector = [[embedder.wv.get_vector(token) for token in word_tokenize(sentence)] for sentence in sentences]

        return vector



class DataLoader:
    '''A class which holds functionality to load and interact with the data from the research article'''
    def __init__(self, dataset = 'genmymodel'):
        # Prepare tqdm loops
        tqdm.pandas()

        # Set target data file
        if dataset == 'lindholmen':
            print('Continuing with the Lindholmen dataset')
            self.data_link = '../../data/uml_extracted_metadata_annotated.json'
        elif dataset == 'genmymodel':
            print('Continuing with the GenMyModel dataset')
            self.data_link = '../../data/genmymodel_uml_extracted_metadata_annotated.json'
        else:
            raise ValueError('This dataset is not supported. Please only use \'lindholmen\' or \'genmymodel\' as keywords.')

        # Set target directory for saving embeddings
        self.data_dir = '../embeddings/' + dataset 

        # Create destination if it doesn't exist
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

        # Clean classes and attributes from training data
        self.data = self.get_cleaned_data()

        # All the classes and attributes, used for training models
        self.df = self.get_df_from_data()

        # Set embedding functions
        self.set_embeddings()
    
    def get_cleaned_data(self):
        '''Returns a dictionary with the harvested and cleaned classes and attributes to be used in classification'''
        with open(self.data_link) as json_file:
            # Load data as dictionary
            data = json.load(json_file)

            # Only keep English classes and attributes
            english_data = {
                file: data[file]
                for file in data.keys()
                if data[file]['lang'] == '__label__en'
            }
            
            return english_data
    
    def get_df_from_data(self):
        '''Returns a dataframe with both the classes and the attributes'''
        # Store all classes and attributes independent of eachother
        all_classes = []
        all_attrs = []

        # Loop over all metadata and append to proper list
        for file, metadata in self.data.items():
            if 'classes' in metadata.keys():
                all_classes.append(metadata['classes'])
            
            if 'attributes' in metadata.keys():
                all_attrs.append(metadata['attributes'])

        # Create big dataframe with all values together
        flatten = lambda t: np.array([item for sublist in t for item in sublist])
        return pd.DataFrame(list(map(lambda x: [x, 'class'], np.unique(flatten(all_classes)))) + list(map(lambda x: [x, 'attribute'], np.unique(flatten(all_attrs)))), columns=['name', 'type'])

    def set_embeddings(self):
        '''Set all interfaces for embedding techniques using custom functions or Flair encoders'''
        
        def get_flair_embedding(embedding):
            encoder = FlairEncoder(embedding = embedding, data_dir = self.data_dir, data = self.df)
            return encoder.get_embedded_dataset
        
        def get_fasttext_embedding():
            encoder = FastTextEncoder(data_dir = self.data_dir, data = self.df) 
            return encoder.get_embedded_dataset

        def get_word2vec_embedding():
            encoder = Word2VecEncoder(data_dir = self.data_dir, data = self.df) 
            return encoder.get_embedded_dataset

        # Attach all function references
        self.get_bert = get_flair_embedding('bert-base-uncased')
        self.get_transformerxl = get_flair_embedding('transfo-xl-wt103')
        self.get_gpt = get_flair_embedding('openai-gpt')
        self.get_gpt2 = get_flair_embedding('gpt2')
        self.get_xlm = get_flair_embedding('xlm-mlm-en-2048')
        self.get_xlnet = get_flair_embedding('xlnet-base-cased')
        self.get_gptneo = get_flair_embedding('EleutherAI/gpt-neo-1.3B')
        self.get_fasttext = get_fasttext_embedding()
        self.get_word2vec = get_word2vec_embedding()
    
    @staticmethod
    def apply_pooling(technique, df):
        '''Functionality to apply a pooling technique to a dataframe'''
        def pooling(vector):
            if technique == 'max':
                # Max pooling
                if len(vector) > 1:
                    return [row.max() for row in np.transpose([[token_row.max() for token_row in np.transpose(np.array(sentence))] for sentence in vector])]
                else:
                    return [token_row.max() for token_row in np.transpose(vector[0])]
            elif technique == 'min':
                # Min pooling
                if len(vector) > 1:
                    return [row.min() for row in np.transpose([[token_row.min() for token_row in np.transpose(np.array(sentence))] for sentence in vector])]
                else:
                    return [token_row.min() for token_row in np.transpose(vector[0])]
            elif technique == 'average':
                # Average pooling
                if len(vector) > 1:
                    return [np.average(row) for row in np.transpose([[np.average(token_row) for token_row in np.transpose(np.array(sentence))] for sentence in vector])]
                else:
                    return [np.average(token_row) for token_row in np.transpose(vector[0])]
            else:
                raise ValueError('This pooling technique has not been implemented. Please only use \'min\', \'max\' or \'average\' as keywords.')

        def init():
            '''Execute all logic'''
            print('Applying ' + technique + ' pooling to the dataset...')
            df.embedding = df.embedding.progress_apply(lambda embedding: pooling(embedding))
            return df 

        return init()
