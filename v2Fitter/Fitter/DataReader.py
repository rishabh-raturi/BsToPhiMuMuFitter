#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set sw=4 ts=4 fdm=indent fdl=1 fdn=3 ft=python et:

# Description     : Creating RooDataSet for fitting
# Author          : Po-Hsun Chen (pohsun.chen.hep@gmail.com)
# Last Modified   : 20 Feb 2019 19:06 17:36

from v2Fitter.FlowControl.Path import Path

import os, pdb, tempfile
import ROOT
from ROOT import TChain
from ROOT import TIter
from ROOT import RooDataSet
from BsToPhiMuMuFitter.varCollection import Bmass

class DataReader(Path):
    """Create RooDataSet from a TChain"""
    def __init__(self, cfg):
        """Init"""
        super(DataReader, self).__init__(cfg)
        self.argset = cfg['argset']
        self.reset()
        return

    def reset(self):
        super(DataReader, self).reset()
        self.ch = None
        self.friend = None
        self.dataset = {}

    def __str__(self):
        list_of_files = self.ch.GetListOfFiles()
        next_file = TIter(list_of_files)
        print("Input file list is given below.")
        for f in range(list_of_files.GetEntries()):
            print("\t{0}".format(next_file().GetTitle()))
        print("End of the input file list.")
        return ""

    @classmethod
    def templateConfig(cls):
        cfg = {
            'name': "DataReader",
            'ifile': [],
            'ifriend': [],
            'ifriendIndex': ["Run", "Event"],
            'argset': [],
            'dataset': [],
            'preloadFile': None,
        }
        return cfg

    def createDataSet(self, dname, dcut):
        print("""Return named dataset, create if not exist""")
        if dname in self.dataset.keys():
            return self.dataset[dname]
        tempfile_preload = ROOT.TFile(tempfile.gettempdir()+"/temp.root", 'RECREATE') #Pritam
        data = RooDataSet(
            dname,
            "",
            self.ch,
            self.argset,
            dcut)
        data.Write(); tempfile_preload.Close() #Pritam
        self.dataset[dname] = data
        print("ARGSET: ", self.argset, dcut)
        return data

    def createDataSets(self, dataset):
        print("""Get named dataset""")
        for name, cut in dataset:
            if self.cfg['preloadFile'] and os.path.exists(self.cfg['preloadFile']):
                file_preload = ROOT.TFile(self.cfg['preloadFile'])
                data = file_preload.Get(name)
                if not data == None:
                    self.dataset[name] = data
                file_preload.Close()
            self.createDataSet(name, cut)
        if self.process.cfg['seqKey']=="fitSigMBinned": self.createBHist(cut)
        return self.dataset
    
    def createBHist(self, cut):
        h_Bmass=ROOT.TH1D("h_Bmass", "", 18, 4.9, 5.8)
        self.ch.Draw("Bmass>>h_Bmass", cut)
        self.cfg['source']['h_Bmass']=h_Bmass

    def _runPath(self):
        self.ch = TChain()

        print "Name: ", self.cfg['name']
        for f in self.cfg['ifile']:
            #self.ch.SetName(flie.GetListOfKeys().At(0).GetName())
            self.ch.Add(f)
        if len(self.cfg['ifriend']) > 0:
            self.friend = TChain("tree")
            for f in self.cfg['ifriend']:
                self.friend.Add(f)
            self.friend.BuildIndex(*self.cfg['ifriendIndex'])
            self.ch.AddFriend(self.friend)
        self.createDataSets(self.cfg['dataset'])
        pass

    def _addSource(self):
        print("""Add dataset and arguments to source pool""")
        print("source: cfg", self.cfg['source'])
        if self.cfg['preloadFile'] and not os.path.exists(self.cfg['preloadFile']):
            file_preload = ROOT.TFile(self.cfg['preloadFile'], 'RECREATE')
            for dname, d in self.dataset.items():
                d.Write()
            file_preload.Close()

        if not 'source' in self.cfg.keys():
            self.cfg['source'] = {}
        #self.cfg['source']['{0}.tree'.format(self.name)] = self.ch
        self.cfg['source']['{0}.argset'.format(self.name)] = self.argset
        if len(self.cfg['ifriend']) > 0:
            self.cfg['source']['{0}.friend'.format(self.name)] = self.friend
        for dname, d in self.dataset.items():
            self.cfg['source'][dname] = d
            self.logger.logINFO("{0} events in {1}.".format(d.sumEntries(), dname))
        super(DataReader, self)._addSource()
        print("source: cfg", self.cfg['source'])
