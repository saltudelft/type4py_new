from os.path import join
from sklearn.metrics import classification_report
import pickle
import re
import numpy as np

def eval_type_embed(y_pred: np.array, y_true: np.array, common_types: set, top_n: int=10):

    all_common_types = 0
    corr_common_types = 0
    all_rare_types = 0
    corr_rare_types = 0

    # Mask arrays to keep location correct predictions
    corr_common_mask = np.array([False] * len(y_pred), dtype=np.bool)
    corr_rare_mask = np.array([False] * len(y_pred), dtype=np.bool)

    for idx, p in enumerate(y_pred):
        
        if y_true[idx] in common_types:
            all_common_types += 1
            if y_true[idx] in p[:top_n]:
                corr_common_types += 1
                corr_common_mask[idx] = True
        else:
            all_rare_types += 1
            if y_true[idx] in p[:top_n]:
                corr_rare_types += 1
                corr_rare_mask[idx] = True

    return (corr_common_types + corr_rare_types) / len(y_pred) * 100.0 ,corr_common_types / all_common_types * 100.0, \
            corr_rare_types / all_rare_types * 100.0, corr_common_mask, corr_rare_mask

def eval_parametric_match(y_pred: np.array, y_true: np.array, common_types: set, top_n: int=10):
    """
    Finds correct parametric types in predicted types. That is, List[*] is parametric type.
    Only outermost is considered, which is List in the given example.
    """

    all_param_common_types = 0
    corr_param_common_types = 0
    all_param_rare_types = 0
    corr_param_rare_types = 0
    param_type_match = r'(.+)\[(.+)\]'

    def pred_param_types(pred_types: np.array, true_param_type):
        no_match = 0
        for p in pred_types:
            if re.match(param_type_match, p):
                if true_param_type.group(1) == re.match(param_type_match, p).group(1):
                    no_match += 1
                    break
        
        return no_match

    for idx, t in enumerate(y_true):
        matched_param_type = re.match(param_type_match, t)
        if t in common_types:
            all_param_common_types += 1
            if t in y_pred[idx][:top_n]:
                corr_param_common_types += 1
            elif matched_param_type:
                corr_param_common_types += pred_param_types(y_pred[idx], matched_param_type)

        else:
            all_param_rare_types += 1
            if t in y_pred[idx][:top_n]:
                corr_param_rare_types += 1
            elif matched_param_type:
                corr_param_rare_types += pred_param_types(y_pred[idx], matched_param_type)

    return (corr_param_common_types + corr_param_rare_types) / len(y_pred) * 100.0 ,corr_param_common_types / all_param_common_types * 100.0, \
            corr_param_rare_types / all_param_rare_types * 100.0

def eval_pred_dsl(y_true, y_pred, top_n=10):
    """
    Computes evaluation metrics such as recall, precision and f1-score
    """

    def pred_types_fix(y_true, y_pred):
        best_predicted = np.empty_like(y_true)
        for i in range(y_true.shape[0]):
            if y_true[i] in y_pred[i][:top_n]:
                best_predicted[i] = y_true[i]
            else:
                best_predicted[i] = y_pred[i][0]

        return best_predicted
    
    y_pred_fixed = pred_types_fix(y_true, y_pred)
    report = classification_report(y_true, y_pred_fixed, output_dict=True)

    return report['weighted avg']

def evaluate(output_path: str, data_loading_funcs: dict, top_n: int=10):

    # Loading label encoder andd common types
    le_all = pickle.load(open(join(output_path, "label_encoder_all.pkl"), 'rb'))
    common_types = pickle.load(open(join(output_path, f"{data_loading_funcs['name']}_common_types.pkl"), 'rb'))

    pred_test_embed = np.load(join(output_path, f"type4py_{data_loading_funcs['name']}_pred.npy"), allow_pickle=True)
    embed_test_labels = np.load(join(output_path, f"type4py_{data_loading_funcs['name']}_true.npy"))

    acc_all, acc_common, acc_rare, com_mask, rare_mask = eval_type_embed(pred_test_embed,
                                                                     embed_test_labels,
                                                                     common_types, top_n)

    print("Type4Py - Exact match - all: %.2f%%" % acc_all)
    print("Type4Py - Exact match - common: %.2f%%" % acc_common)
    print("Type4Py - Exact match - rare: %.2f%%" % acc_rare)

    pred_test_embed_inv = np.array([le_all.inverse_transform(pred) for pred in pred_test_embed])
    embed_test_labels_inv = np.array([le_all.inverse_transform([t])[0] for t in embed_test_labels])
    common_types_inv = np.array([le_all.inverse_transform([c])[0] for c in common_types])

    acc_all_param, acc_common_param, acc_rare_param = eval_parametric_match(pred_test_embed_inv,
                                                                            embed_test_labels_inv,
                                                                            common_types_inv, top_n)

    print("Type4Py - Parametric match - all: %.2f%%" % acc_all_param)
    print("Type4Py - Parametric match - common: %.2f%%" % acc_common_param)
    print("Type4Py - Parametric match - rare: %.2f%%" % acc_rare_param)

    res = eval_pred_dsl(embed_test_labels, pred_test_embed, top_n=top_n)

    print("F1-score: %.2f | Recall: %.2f | Precision: %.2f" % (res['f1-score']*100,
                                                               res['recall']*100,
                                                               res['precision']*100))