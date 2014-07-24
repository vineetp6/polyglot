#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""template.py: Description of what the module does."""

from io import open
import logging

import numpy as np
from numpy import float32

from six import text_type as unicode
from six import iteritems

from base import CountedVocabulary, OrderedVocabulary


logger = logging.getLogger(__name__)


def _open(file_, mode='r'):
  if isinstance(file_, unicode):
    return open(file_, mode)
  return file_


class Embedding(object):
  """ Mapping a vocabulary to a d-dimensional points."""

  def __init__(self, vocabulary, vectors):
    self.vocabulary = vocabulary
    self.vectors = np.asarray(vectors)

    if len(self.vocabulary) != self.vectors.shape[0]:
      raise ValueError("Vocabulary has {} items but we have {} "
                       "vectors".format(len(vocabulary), self.vectors.shape[0]))

  def __getitem__(self, k):
    return self.vectors[self.vocabulary[k]]

  def __contains__(self, k):
    return k in self.vocabulary

  def __delitem__(self, k):
    """Remove the word and its vector from the embedding.

    Note:
     This operation costs \\theta(n). Be careful putting it in a loop.
    """
    index = self.vocabulary[k]
    del self.vocabulary[k]
    self.vectors = np.delete(self.vectors, index, 0)

  def __len__(self):
    return len(self.vocabulary)

  def __iter__(self):
    for w in self.vocabulary:
      yield w, self[w]

  @property
  def words(self):
    return self.vocabulary.words

  @property
  def shape(self):
    return self.vectors.shape

  def most_frequent(self, k, inplace=False):
    """Only most frequent k words to be included in the embeddings."""
    vocabulary = self.vocabulary.most_frequent(k)
    vectors = np.asarray([self[w] for w in vocabulary])
    if inplace:
      self.vocabulary = vocabulary
      self.vectors = vectors
      return self
    return Embedding(vectors=vectors, vocabulary=vocabulary)

  @staticmethod
  def from_gensim(model):
    word_counts = {}
    vectors = []
    for word, vocab in sorted(iteritems(model.vocab), key=lambda item: -item[1].count):
      vectors.append(model.syn0[vocab.index])
      word_count[word] = vocab.count
    vocab = CountedVocabulary(word_count=word_count)
    vectors = np.asarray(vectors)
    return Embedding(vocabulary=vocab, vectors=vectors)

  @staticmethod
  def _from_word2vec_vocab(fvocab):
    counts = {}
    with _open(fvocab) as fin:
      for line in fin:
        word, count = unicode(line).strip().split()
        counts[word] = int(count)
    return CountedVocabulary(word_count=counts)

  @staticmethod
  def _from_word2vec_binary(fname):
    with _open(fname, 'rb') as fin:
      words = []
      header = unicode(fin.readline())
      vocab_size, layer1_size = map(int, header.split()) # throws for invalid file format
      vectors = np.zeros((vocab_size, layer1_size), dtype=float32)
      binary_len = np.dtype(float32).itemsize * layer1_size
      for line_no in xrange(vocab_size):
        # mixed text and binary: read text first, then binary
        word = []
        while True:
          ch = fin.read(1)
          if ch == b' ':
            break
          if ch != b'\n': # ignore newlines in front of words (some binary files have newline, some don't)
            word.append(ch)
        word = unicode(b''.join(word))
        index = line_no
        words.append(word)
        vectors[index, :] = np.fromstring(fin.read(binary_len), dtype=float32)
      return words, vectors

  @staticmethod
  def _from_word2vec_text(fname):
    with _open(fname) as fin:
      words = []
      header = unicode(fin.readline())
      vocab_size, layer1_size = map(int, header.split()) # throws for invalid file format
      vectors = np.zeros((vocab_size, layer1_size), dtype=float32)
      for line_no, line in enumerate(fin):
        parts = unicode(line).split()
        if len(parts) != layer1_size + 1:
          raise ValueError("invalid vector on line %s (is this really the text format?)" % (line_no))
        word, weights = parts[0], map(float32, parts[1:])
        index = line_no
        words.append(word)
        vectors[index,:] = weights
      return words, vectors

  @staticmethod
  def from_word2vec(fname, fvocab=None, binary=False):
    """
    Load the input-hidden weight matrix from the original C word2vec-tool format.

    Note that the information stored in the file is incomplete (the binary tree is missing),
    so while you can query for word similarity etc., you cannot continue training
    with a model loaded this way.

    `binary` is a boolean indicating whether the data is in binary word2vec format.
    Word counts are read from `fvocab` filename, if set (this is the file generated
    by `-save-vocab` flag of the original C tool).
    """
    vocabulary = None
    if fvocab is not None:
      logger.info("loading word counts from %s" % (fvocab))
      vocabulary = Embedding._from_word2vec_vocab(fvocab)

    logger.info("loading projection weights from %s" % (fname))
    if binary:
      words, vectors = Embedding._from_word2vec_binary(fname)
    else:
      words, vectors = Embedding._from_word2vec_text(fname)

    if not vocabulary:
      vocabulary = OrderedVocabulary(words=words)

    return Embedding(vocabulary=vocabulary, vectors=vectors)