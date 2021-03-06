
import copy
import numpy as np
import pandas as pd
import pdb
import sklearn

class CrossPredict(object):
    ''' Facilitate cross-validation for an arbitrary learner.
    This computes folds, fits a learner on each fold, and gathers the predictions
    on each hold-out set. It does not do any evaluation of those predictions '''
    def __init__(self, data, Learner, hyperparameters = None, n_fold = 5, verbose = 0):
        '''
        :param data: list containing numeric features 'X' as pandas DataFrame and labels 'y' as numeric numpy array
        :param Learner: Any of the learner classes defined in ./learners.py
        :param verbose: (integer) verbosity level
        '''
        self.data = data
        self.params = hyperparameters
        self.Learner = Learner
        self.verbose = verbose
        # Generate data folds
        np.random.seed(0)
        kfs = sklearn.model_selection.StratifiedKFold(n_splits=n_fold, shuffle=True)
        self.folds = [
            {'train': train_index, 'test': test_index}
            for train_index, test_index in kfs.split(self.data.X, self.data.group)
        ]
        # Keep track of indices and their relationship to essay sets
        self.keys = pd.DataFrame({
            'essay_set': data.group,
            'ref': list(range(len(data.y)))
        })
        # Check integrity of CV structure
        _ = self.analyze_cross_predict_structure()

    def _train_and_predict(self, train_idx, test_idx):
        ''' Train a classifier on the data corresponding to the rows in `idx` '''
        train_data = self.data.select(train_idx)
        test_data = self.data.select(test_idx)
        learner = self.Learner(params = copy.deepcopy(self.params))
        learner.train(train_data)
        return pd.DataFrame({
            'pred': learner.predict(test_data.X),
            'truth': test_data.y,
            'idx': test_idx,
            'essay_set': self.keys.essay_set[test_idx]
        })

    def _train_and_predict_one_fold(self, k):
        '''
        :param k: (integer) which fold
        '''
        if self.verbose:
            print('training fold ' + str(k))
        trn = self.folds[k]['train']
        tst = self.folds[k]['test']
        # Currently we're fitting a totally separate model for each essay set, so
        #   here we iterate over the essay sets:
        trn_es = self.keys.iloc[trn].groupby('essay_set')
        tst_es = self.keys.iloc[tst].groupby('essay_set')
        essays = tst_es.groups.keys()
        assert essays == trn_es.groups.keys() # in case cv-split was terribly uneven -- ideally should stratify it
        return pd.concat([self._train_and_predict(
            trn_es.get_group(e).ref, tst_es.get_group(e).ref) for e in essays])

    def cross_predict(self):
        kr = range(len(self.folds))
        preds = pd.concat([self._train_and_predict_one_fold(k) for k in kr])
        return preds.sort_values('idx')

    def _count_per_essay_set(self, k, rows):
        cdf = pd.DataFrame([[k, e, len(g)] for e, g in self.keys.iloc[rows].groupby('essay_set')])
        cdf.columns = ['fold', 'essay_set', 'count']
        return cdf.sort_values('essay_set')

    def analyze_cross_predict_structure(self):
        ''' Sanity checks to ensure that the cv folds are working as expected '''
        train_counts = pd.concat([self._count_per_essay_set(k, f['train'])
                                  for k, f in enumerate(self.folds)])
        train_counts.rename({'count': 'train_count'}, inplace = True, axis = 1)
        test_counts = pd.concat([self._count_per_essay_set(k, f['test'])
                                 for k, f in enumerate(self.folds)])
        test_counts.rename({'count': 'test_count'}, inplace=True, axis=1)
        df = train_counts.merge(test_counts, on=['fold', 'essay_set'], how='inner')
        ratios = df.train_count/df.test_count
        max_ratio = ratios.max()
        min_ratio = ratios.min()
        assert max_ratio/min_ratio < 1.02
        if self.verbose:
            print('Cross predict involves fitting and predicting with ' + str(df.shape[0]) +
                  ' different models,\n   one for every fold-essay set combination')
            print('The ratio of training data to testing data in the folds ranges\n   from ' +
                  str(min_ratio) + " to " + str(max_ratio))
        return df

    def cheat(self):
        '''
        Use test = train and with no folds. This basically computes the 'fitted values' for the learner
        '''
        trn_es = self.keys.groupby('essay_set')
        tst_es = self.keys.groupby('essay_set')
        essays = tst_es.groups.keys()
        return pd.concat([self._train_and_predict(
            trn_es.get_group(e).ref, tst_es.get_group(e).ref) for e in essays])
