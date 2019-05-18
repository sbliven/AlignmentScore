#!/usr/bin/env python3
"""Tree testing"""

import os, re, sys, Bio.Align, argparse, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from Bio import AlignIO
from Bio import Phylo
from AlignmentGroup import AlignmentGroup
from Bio.Phylo.TreeConstruction import DistanceCalculator
from Bio.Phylo.TreeConstruction import DistanceTreeConstructor


import PhyMeas

def create_and_parse_argument_options(argument_list):
	parser = argparse.ArgumentParser(description='Calculate importance of sequences based on phylogenetic tree.')
	parser.add_argument('alignment_file', help='Path to alignment file')
	commandline_args = parser.parse_args(argument_list)
	return commandline_args

def tree_contruct(aln_obj, nj=False):
	'''
	Constructs and returns a tree from an alignment object.
	'''
	calculator = DistanceCalculator('blosum62')
	dist_mx = calculator.get_distance(aln_obj)
	constructor = DistanceTreeConstructor()
	if nj:
		tree = constructor.nj(dist_mx)
	else:
		tree = constructor.upgma(dist_mx)
	tree.ladderize()
	#print(Phylo.draw_ascii(tree))
	return tree

def find_deepest_ancestors(tree):
	'''
	Finds and returns a dictionary with keys the deepest ancestors and values their children.
	'''
	treedepths_int = tree.depths(unit_branch_lengths=True)
	treedepths = tree.depths()
	common_ancestors=[]
	deepestanc_to_child={}
	for anc in treedepths:
		if treedepths_int[anc] == 1:
			#print(anc,treedepths[anc],treedepths_int[anc])
			for child in tree.get_terminals():
				if anc.is_parent_of(child):
					if anc not in deepestanc_to_child:
						deepestanc_to_child[anc]=[]
					deepestanc_to_child[anc].append(child.name)
	
	return deepestanc_to_child

def slice_by_anc(unsliced_aln_obj, deepestanc_to_child):
	'''
	Slices an alignment into different alignments
	by the groupings defined in deepestanc_to_child.
	'''
	##Could be very buggy if there is no name splitting.
	##Make sure you add exceptions to handle cases where there is no common name in the group
	##or the names accross groups are the same.
	anc_names={}
	sliced_dict={}
	for anc in deepestanc_to_child:
		anc_names[anc] = os.path.commonprefix(deepestanc_to_child[anc])[:-1]
	####
	####


	if len(anc_names) != 2:
		raise ValueError("For now does not support more than two groups! Offending groups are "+str(', '.join(anc_names.values())))
	
	for anc in deepestanc_to_child:
		what = Bio.Align.MultipleSeqAlignment([])
		for entry in unsliced_aln_obj:
			if entry.id in deepestanc_to_child[anc]:
				what.append(entry)
		sliced_dict[anc_names[anc]]=what
	return sliced_dict

def generate_weight_vectors(tree):
	treedepths_int = tree.depths(unit_branch_lengths=True)
	treedepths = tree.depths()
	dict_clades = {}
	for terminal_leaf in tree.get_terminals():
		dict_clades[terminal_leaf.name] = terminal_leaf
	wei_vr = []
	for leaf in sorted(dict_clades):
		#wei_vr.append((1/2**treedepths_int[dict_clades[leaf]]))		#Accounting for topology of tree
		wei_vr.append(treedepths[dict_clades[leaf]])
		#print(leaf, treedepths[dict_clades[leaf]])
		#print (leaf, 1/2**treedepths_int[dict_clades[leaf]])
	return wei_vr

def main(commandline_arguments):
	comm_args = create_and_parse_argument_options(commandline_arguments)
	alignIO_out = PhyMeas.read_align(comm_args.alignment_file)
	#sliced_alns = PhyMeas.slice_by_name(alignIO_out)

	tree = tree_contruct(alignIO_out)
	deepestanc_to_child = find_deepest_ancestors(tree)
	sliced_dict = slice_by_anc(alignIO_out, deepestanc_to_child)
	
	wei_vr_dict = {}
	for alngroup_name in sliced_dict:
		tree = tree_contruct(sliced_dict[alngroup_name])
		wei_vr_dict[alngroup_name] = generate_weight_vectors(tree)
	
	#for group in wei_vr_dict:
	#	print(group, sum(wei_vr_dict[group]))
	#	print(group, [x / max(wei_vr_dict[group]) for x in wei_vr_dict[group]])

if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))