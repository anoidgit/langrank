import lang2vec.lang2vec as l2v
import numpy as np
import pkg_resources
import os
import lightgbm as lgb

TASKS = ["MT","DEP","EL","POS"]

MT_DATASETS = {
	"ted" : "ted.npy",
}

MT_MODELS = {
	"all" : "all.lgbm",
	"geo" : "geo.lgbm",
	"best": "lgbm_model_mt_slv.txt",
}

POS_DATASETS = {}
EL_DATASETS = {}
DEP_DATASETS = {}

POS_MODELS = {}
EL_MODELS = {}
DEP_MODELS = {}

# checks
def check_task(task):
	if task not in TASKS:
		raise Exception("Unknown task " + task + ". Only 'MT', 'DEP', 'EL', 'POS' are supported.")

def check_task_model(task, model):
	check_task(task)
	avail_models = map_task_to_models(task)
	if model not in avail_models:
		ll = ', '.join([key for key in avail_models])
		raise Exception("Unknown model " + model + ". Only "+ll+" are provided.")

def check_task_model_data(task, model, data):
	check_task_model(task, model)
	avail_data = map_task_to_data(task)
	if data not in avail_data:
		ll = ', '.join([key for key in avail_data])
		raise Exception("Unknown dataset " + data + ". Only "+ll+" are provided.")


# utils
def map_task_to_data(task):
	if task == "MT":
		return MT_DATASETS
	elif task == "POS":
		return POS_DATASETS
	elif task == "EL":
		return EL_DATASETS
	elif task == "DEP":
		return DEP_DATASETS
	else:
		raise Exception("Unknown task")

def map_task_to_models(task):
	if task == "MT":
		return MT_MODELS
	elif task == "POS":
		return POS_MODELS
	elif task == "EL":
		return EL_MODELS
	elif task == "DEP":
		return DEP_MODELS
	else:
		raise Exception("Unknown task")

def read_vocab_file(fn):
	with open(fn) as inp:
		lines = inp.readlines()
	c = []
	v = []
	for l in lines:
		l = l.strip().split()
		if len(l) == 2:
			c.append(int(l[1]))
			v.append(l[0])
	return v,c


# used for ranking
def get_candidates(task, languages=None):
	if languages is not None and not isinstance(languages, list):
		raise Exception("languages should be a list of ISO-3 codes")

	datasets_dict = map_task_to_data(task)
	cands = []
	for dt in datasets_dict:
		fn = pkg_resources.resource_filename(__name__, os.path.join('indexed', task, datasets_dict[dt]))
		d = np.load(fn, encoding='latin1').item()
		cands += [(key,d[key]) for key in d if key != "eng"]

	# Possibly restrict to a subset of candidate languages
	if languages is not None:
		# Keep a candidate if it matches the languages
		new_cands = [c for c in cands if c[0][-3:] in languages]
		return new_cands

	return cands

# prepare new dataset
def prepare_new_dataset(lang, dataset_source=None, dataset_target=None, dataset_subword_source=None, dataset_subword_target=None):
	features = {}
	features["lang"] = lang
	# Get URIEL features -- not needed!
	#features["geological"] = l2v.get_features(lang, "geo")
	#features["genetic"] = l2v.get_features(lang, "fam")
	#features["inventory"] = l2v.get_features(lang, "inventory_average")
	#features["phonology"] = l2v.get_features(lang, "phonology_average")
	#features["syntax"] = l2v.get_features(lang, "syntax_average")
	#features["learned"] = l2v.get_features(lang, "learned")


	# Get dataset features
	if dataset_source is None and dataset_target is None and dataset_subword_source is None and dataset_subword_target is None:
		print("NOTE: no dataset provided. You can still use the ranker using language typological features.")
		return features
	elif dataset_source is None: # and dataset_target is None:
		print("NOTE: no word-level dataset provided, will only extract subword-level features.")
	elif dataset_subword_source is None: # and dataset_subword_target is None:
		print("NOTE: no subword-level dataset provided, will only extract word-level features.")


	source_lines = []
	if isinstance(dataset_source, str):
		with open(dataset_source) as inp:
			source_lines = inp.readlines()
	elif isinstance(dataset_source, list):
		source_lines = dataset_source
	else:
		raise Exception("dataset_source should either be a filnename (str) or a list of sentences.")
	'''
	if isinstance(dataset_target, str):
		with open(dataset_target) as inp:
			target_lines = inp.readlines()
	elif isinstance(dataset_target, list):
		source_lines = dataset_target
	else:
		raise Exception("dataset_target should either be a filnename (str) or a list of sentences.")
	'''
	if source_lines:
		features["dataset_size"] = len(source_lines)
		tokens = [w for s in source_lines for w in s.strip().split()]
		features["token_number"] = len(tokens)
		types = set(tokens)
		features["type_number"] = len(types)
		features["word_vocab"] = types
		features["type_token_ratio"] = features["type_number"]/float(features["token_number"])

	if isinstance(dataset_subword_source, str):
		with open(dataset_subword_source) as inp:
			source_lines = inp.readlines()
	elif isinstance(dataset_subword_source, list):
		source_lines = dataset_subword_source
	elif dataset_subword_source is None:
		pass
		# Use the word-level info, just in case. TODO(this is only for MT)
		# source_lines = []
	else:
		raise Exception("dataset_subword_source should either be a filnename (str) or a list of sentences.")
	if source_lines:
		features["dataset_size"] = len(source_lines) # This should be be the same as above
		tokens = [w for s in source_lines for w in s.strip().split()]
		features["subword_token_number"] = len(tokens)
		types = set(tokens)
		features["subword_type_number"] = len(types)
		features["subword_vocab"] = types
		features["type_token_ratio"] = features["subword_type_number"]/float(features["subword_token_number"])

	return features

def uriel_distance_vec(languages):
	print('...geographic')
	geographic = l2v.geographic_distance(languages)
	print('...genetic')
	genetic = l2v.genetic_distance(languages)
	print('...inventory')
	inventory = l2v.inventory_distance(languages)
	print('...syntactic')
	syntactic = l2v.syntactic_distance(languages)
	print('...phonological')
	phonological = l2v.phonological_distance(languages)
	print('...featural')
	featural = l2v.featural_distance(languages)
	uriel_features = [featural, genetic, geographic, inventory, phonological, syntactic]
	return uriel_features



def distance_vec(test, transfer, uriel_features):
	output = []
	# Dataset specific 
	# Dataset Size
	transfer_dataset_size = transfer["dataset_size"]
	task_data_size = test["dataset_size"]
	ratio_dataset_size = float(transfer_dataset_size)/task_data_size
	# TTR
	transfer_ttr = transfer["type_token_ratio"]
	task_ttr = test["type_token_ratio"]
	distance_ttr = (1 - transfer_ttr/task_ttr) ** 2
	# Word overlap
	word_overlap = float(len(set(transfer["word_vocab"]).intersection(set(test["word_vocab"])))) / (transfer["type_number"] + test["type_number"])
	# Subword overlap
	subword_overlap = float(len(set(transfer["subword_vocab"]).intersection(set(test["subword_vocab"])))) / (transfer["subword_type_number"] + test["subword_type_number"])

	#l1 = test["lang"]
	#l2 = candidate_language
	# Typological Features
	'''
	geographic = l2v.geographic_distance(l1, l2)
	genetic = l2v.genetic_distance(l1, l2)
	inventory = l2v.inventory_distance(l1, l2)
	syntactic = l2v.syntactic_distance(l1, l2)
	phonological = l2v.phonological_distance(l1, l2)
	featural = l2v.featural_distance(l1, l2)
	'''
	data_specific_features = [word_overlap, subword_overlap, transfer_dataset_size, task_data_size, ratio_dataset_size, transfer_ttr, task_ttr, distance_ttr]
	# uriel_features = [featural, genetic, geographic, inventory, phonological, syntactic]
	
	return np.array(data_specific_features + uriel_features)




	
def rank(test_dataset_features, task="MT", candidates="all", model="best"):
	'''
	test_dataset_features : the output of prepare_new_dataset(). Basically a dictionary with the necessary dataset features.
	'''
	# Checks
	check_task_model(task, model)

	# Get candidates to be compared against
	print("Preparing candidate list...")
	if candidates=='all':
		candidate_list = get_candidates(task)
	else:
		# Restricts to a specific set of languages
		candidate_list = get_candidates(task, candidates)

	print("Collecting URIEL distance vectors...")
	languages = [test_dataset_features["lang"]] + [c[1]["lang"] for c in candidate_list]
	uriel = uriel_distance_vec(languages)


	print("Collecting distance vectors...")
	test_inputs = []
	for i,c in enumerate(candidate_list):
		key = c[0]
		cand_dict = c[1]
		candidate_language = key[-3:]
		uriel_j = [u[0,i+1] for u in uriel]
		distance_vector = distance_vec(test_dataset_features, cand_dict, uriel_j)
		test_inputs.append(distance_vector)
	# Just for testing, print vectors:
	'''
	for c,inp in zip(candidate_list,test_inputs):
		print(c[0]) #key
		print(inp)
		print("*****")
	'''
	# TODO:load model
	print("Loading model...")
	model_dict = map_task_to_models(task) # this loads the dict that will give us the name of the pretrained model
	model_fname = model_dict[model] # this gives us the filename (needs to be joined, see below)
	modelfilename = pkg_resources.resource_filename(__name__, os.path.join('pretrained_models', task, model_fname))
	# TODO: actually load model

	# TODO: rank
	bst = lgb.Booster(model_file=modelfilename)
	
	print("predicting...")
	predict_scores = bst.predict(test_inputs)
	print(predict_scores)

	ind = np.argsort(predict_scores)
	print("Ranking:")
	for j,i in enumerate(ind):
		print("%d. %s : score=%.2f" % (j, candidate_list[i][0], predict_scores[i]))


    #    model.fit(X_train, y_train, group=qgsize_train,
    #              eval_set=[(X_test, y_test)], eval_group=[qgsize_test], eval_at=3,
    #              early_stopping_rounds=40, eval_metric="ndcg", verbose=False)
    #    model.booster_.save_model(os.path.join(output_dir, "lgbm_model_mt_" + lang_set[task_lang_idx] + ".txt"))
	
	# TODO: return ranking

