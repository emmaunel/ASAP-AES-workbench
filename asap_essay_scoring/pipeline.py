'''
A collection of wrappers for other asap_essay_scoring functions to support
operating each function using file(s) input and writing the output to file(s)

These functions make lots of assumptions about the format and contents of input files.
It could make sense to break off this submodule from the main module if asap_essay_scoring
develops into a more general tool (not specific to ASAP-AES)
'''
import gensim
import numpy as np
import pandas as pd
import pdb

from . import data
from . import tokens
from . import utils
from . import vocab

def tokenize(infile, outfile):
    df = data.read_raw_csv(infile)
    tk = tokens.Tokenizer()
    doc_list = tk.apply_tokenize(df.essay)
    utils.json_save(doc_list, outfile)

def token_features(infile, outfile):
    doc_list = utils.json_load(infile)
    df = pd.DataFrame({
        'word_len_mean': [np.mean([len(t) for t in essay]) for essay in doc_list],
        'word_len_std': [np.std([len(t) for t in essay]) for essay in doc_list]
    })
    df.to_csv(outfile, index=False)
    #pdb.set_trace()

def reduce_docs_to_smaller_vocab(infile, outfile, target_file = None):
    '''
    Simplify a list of tokenized documents by reducing the vocabulary size
    :param infile: List of tokenized docs, the basis for the reduced vocabulary. If `target_file` is None,
    then the simplified version of `infile` is what will get written to `outfile`
    :param outfile: Where to write output
    :param target_file: If specified, this is the collection of documents that will be reduce (instead of `infile`),
    but `infile` is still the basis for the vocab
    '''
    doc_list = utils.json_load(infile)
    vc = vocab.Vocab(vocab_size=3000)
    vc.build_from_tokenized_docs(doc_list)
    if target_file is not None:
        target_docs = utils.json_load(target_file)
        reduced_docs = vc.reduce_docs(target_docs)
    else:
        reduced_docs = vc.reduce_docs(doc_list)
    utils.json_save(reduced_docs, outfile)

def fit_word2vec(infile, outfile):
    reduced_docs = utils.json_load(infile)
    # Abusing tools here slightly: Word2Vec expects a list of sentences, but we're providing
    #   a list of documents instead, pretending that each document is a single sentence. The
    #   fact that we include punctuation as tokens in our tokenization may help to preserve
    #   the sentence structure that we're otherwise ignoring
    wv = gensim.models.word2vec.Word2Vec(reduced_docs, size = 100, iter = 25)
    vocab = list(wv.wv.vocab.keys())
    df = pd.DataFrame([wv.wv.word_vec(w) for w in vocab], index=vocab)
    df.to_csv(outfile, index = True)

def essay_features_from_word2vec(word2vec_infile, reduced_docs_infile, outfile):
    reduced_docs = utils.json_load(reduced_docs_infile)
    embedding = pd.read_csv(word2vec_infile, index_col = 0)
    dft = vocab.DocFeaturizer(vocab_embedding=embedding)
    df = dft.featurize_corpus(reduced_docs)
    df.to_csv(outfile, index = False)

def fit_doc2vec(infile, outfile):
    corpus = [
        gensim.models.doc2vec.TaggedDocument(doc, [i])
        for i, doc in enumerate(utils.json_load(infile))
    ]
    print("building doc2vec vocab")
    model = gensim.models.doc2vec.Doc2Vec(vector_size=50, epochs=55)
    model.build_vocab(corpus)
    print("fitting doc2vec model")
    model.train(corpus, total_examples=model.corpus_count, epochs=model.epochs)
    model.save("model_temp")
    df = pd.DataFrame([model.docvecs[c.tags[0]] for c in corpus])
    df.rename(columns = {k: 'docvec_' + str(k) for k in range(df.shape[1])}, inplace = True)
    df.to_csv(outfile, index=False)