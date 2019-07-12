#!/usr/bin/env python3
"""
Generate SVM from alignment segments.
Two modes:
    Train: Computes a decision function from csv generated with MultiPhyMeas
    Test: Evaluates alignment entries in csv with a provided decision function
"""
#print(__doc__)
import re, sys, csv, argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn import svm
from statistics import mean 
import _pickle as cPickle

def create_and_parse_argument_options(argument_list):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('csv_path', help='Path to csv file storing alignment segment data')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('-tr','--train',help='Provide path to save classifier as a pickle binary file', type=str)
    mode.add_argument('-te','--test',help='Provide path to classifier pickle binary file', type=str)
    parser.add_argument('-pd','--plot_df', help='Path to output plot for the decision function.', type=str)
    parser.add_argument('-mf','--max_features',nargs='+',help='If running in test mode, the program requires the maximal values for each feature class used to generate the decision funciton. 0.338709677419 193.129428571 42')
    commandline_args = parser.parse_args(argument_list)
    return commandline_args, parser

def load_our_data(csv_location):
    '''
    Reads a csv outputted from MultiPhyMeas.py, entries starting with A_ and B_ are considered as + data
    and entries starting with C_ and D_ as - data. Normalizes all the data for x and y in the range 0,1
    using the max(x) and max(y).
    '''
    data_xyz = []
    data_identity = []
    data_weights = []
    with open(csv_location) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count != 0:
                if re.match(r'^A_|^B_',row[0]):
                    data_xyz.append([float(row[2]),float(row[3]),float(row[1])])
                    data_identity.append(1)
                    data_weights.append(row[1])
                elif re.match(r'^C_|^D_',row[0]):
                    data_xyz.append([float(row[2]),float(row[3]),float(row[1])])
                    data_identity.append(0)
                    data_weights.append(float(row[1]))
            line_count+=1
    data_xyz_normx = []
    for tups in data_xyz:
        data_xyz_normx.append([float(tups[0]/max(np.asarray(data_xyz)[:,0])),float(tups[1]/max(np.asarray(data_xyz)[:,1])),float(tups[2]/max(np.asarray(data_xyz)[:,2]))])
    return np.asarray(data_xyz_normx), np.asarray(data_identity), data_weights, max(np.asarray(data_xyz)[:,0]), max(np.asarray(data_xyz)[:,1]), max(np.asarray(data_xyz)[:,2])

def plot_decision_function(classifier,X,y, sample_weight, axis, title, decision_levels=0):
    '''
    Plots the data and the decision function. Besides the classifier function, takes in the sample weights
    and plots it as a size of the datapoints. If they are different than 1.
    '''
    # plot the decision function
    xx, yy, zz = np.meshgrid(np.linspace(0, 1, 100), np.linspace(0, 1, 100), np.linspace(0, 1, 100))
    Z = classifier.decision_function(np.c_[xx.ravel(), yy.ravel(), zz.ravel()])
    print(classifier.score(X, y))
    Z = Z.reshape(xx.shape)
    Z = Z[:,:,0]
    xx = xx[:,:,0]
    yy = yy[:,:,0]
    
    # plot the line, the points, and the nearest vectors to the plane
    if decision_levels != 0:
        axis.contour(xx, yy, Z, colors='r', levels=[0], alpha=0.5, linestyles=['-'])
        axis.contour(xx, yy, Z, colors='b', levels=[decision_levels], alpha=0.5, linestyles=['-'])
    else:
        axis.contour(xx, yy, Z, colors='r', levels=[decision_levels], alpha=0.5, linestyles=['-'])
    #axis.contourf(xx, yy, Z, alpha=0.75, cmap=plt.cm.bone)
    abs_length = [float(n)**2 for n in sample_weight]
    axis.scatter(X[:, 0], X[:, 1], c=y, s=abs_length, alpha=0.9,
                cmap=plt.cm.bone, edgecolors='black')

    #axis.axis('off')
    axis.set_title(title)

def test_function(comm_args, decision_function):
    '''
    Executes prediction and distance calculation on each
    segment from the input for a given decision function.
    '''
    segment_pred_dist = {}
    with open(comm_args.csv_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for entry in csv_reader:
            if line_count != 0:
                #2 features
                #test_segment = np.array([float(entry[2])/float(comm_args.max_features[0]),float(entry[3])/float(comm_args.max_features[1])])
                #3 features
                test_segment = np.array([float(entry[2])/float(comm_args.max_features[0]),float(entry[3])/float(comm_args.max_features[1]),float(entry[1])/float(comm_args.max_features[2])])
                segment_pred = decision_function.predict(test_segment.reshape(1,-1))[0]
                segment_dist = decision_function.decision_function(test_segment.reshape(1,-1))[0]
                if entry[0] not in segment_pred_dist.keys():
                    segment_pred_dist[entry[0]] = []
                segment_pred_dist[entry[0]].append([entry[4],(segment_pred,segment_dist)])
            line_count+=1
    return segment_pred_dist

def mass_test(segment_pred_dist):
    '''For evaluating the decision function with 
    great number of alignments in 4 separate groups.
    '''
    grouped_data={}
    for aln_name in segment_pred_dist:
        dist_sum, pos_sum = 0,0
        if aln_name.split("_")[0] not in grouped_data.keys():
            grouped_data[aln_name.split("_")[0]] = []
        for segm in segment_pred_dist[aln_name]:
            if float(segm[1][0]) == 1:
                pos_sum += 1
                dist_sum+= segm[1][1]
        grouped_data[aln_name.split("_")[0]].append(dist_sum)

    def calc_prec(grouped_data, max_threshold):
        for thr in np.arange(0,max_threshold,0.1):
            tp, tn, fp, fn = 0,0,0,0
            for group in grouped_data.keys():
                if group == 'A' or group == 'B':
                    fn += sum(i<thr for i in grouped_data[group])
                    tp += len(grouped_data[group])-sum(i<thr for i in grouped_data[group])
                if group == 'C' or group == 'D':
                    tn += sum(i<thr for i in grouped_data[group])
                    fp += len(grouped_data[group])-sum(i<thr for i in grouped_data[group])
            print ("Threshold "+str(thr),'\n',"tpr", tp/(tp+fn),"tnr", tn/(tn+fp),'\n',"fnr", fn/(fn+tp),"fpr", fp/(fp+tn),'\n',"precision",tp/(tp+fp))
    calc_prec(grouped_data, 2)

    #fig, axes = plt.subplots(2, 2, sharex=True)
    #fig.subplots_adjust(hspace=0.4, wspace=0.4)
    #axes[0][0].hist(grouped_data['A'])
    #axes[0][0].set_title("Group A")
    #axes[0][1].hist(grouped_data['B'])
    #axes[0][1].set_title("Group B")
    #axes[1][0].hist(grouped_data['C'])
    #axes[1][0].set_title("Group C")
    #axes[1][1].hist(grouped_data['D'])
    #axes[1][1].set_title("Group D")
    #plt.savefig('./outputs/SVM/3ftesting_dataset.png', dpi=600)
    #plt.clf()
#
    #list_for_hist = []
    #for group in sorted(grouped_data.keys()):
    #    list_for_hist.append(grouped_data[group])
    #fig, axes = plt.subplots(1, 1)
    #axes.hist(list_for_hist, label=sorted(grouped_data.keys()),histtype='barstacked', bins=30)
    #axes.legend(prop={'size': 10})
    #plt.savefig('./outputs/SVM/3ftesting_dataset_hists.png', dpi=600)

def main(commandline_arguments):
    '''Main entry point'''
    comm_args, parser = create_and_parse_argument_options(commandline_arguments)

    ### Load alignment segment data  ###
    X = []
    y = []
    X, y, sample_weight, maxX, maxY, maxZ = load_our_data(comm_args.csv_path)

    ### Training mode  ###
    if comm_args.train:
        print("Max on X axis:", maxX, "\nMax on Y axis:", maxY, "\nMax on Z axis:", maxZ)
        
        ### Fit the classifier   ###
        decision_function = svm.SVC(C=10, gamma='auto')
        decision_function.fit(X, y, sample_weight=sample_weight) #Weighted regardless of the fact the weight exist as a third feature.
        #decision_function.d    #Some statistics for the classifier

        ###   Save the classifier   ###
        with open(comm_args.train, 'wb') as fid:
            cPickle.dump(decision_function, fid)

    ### Testing mode  ###
    if comm_args.test:
        if not comm_args.max_features:
            parser.print_help()
            raise ValueError("In test mode providing maximal values for the classifier features is required!")
        decision_function = cPickle.load(open(comm_args.test, 'rb'))
        segment_pred_dist = test_function(comm_args, decision_function)
        mass_test(segment_pred_dist)

    ### Plot the classifier   ###
    if comm_args.plot_df:
        fig, axes = plt.subplots(1, 1, figsize=(7, 7))
        plot_decision_function(decision_function,X,y, sample_weight, axes,
                                    "Decision function", decision_levels=1)
        plt.savefig(comm_args.plot_df, dpi=600)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))