#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set sw=4 ts=4 fdm=indent foldnestmax=3 ft=python et:

import re, pdb
import types
import functools
import itertools
from array import array
from copy import copy
import math

import BsToPhiMuMuFitter.cpp

from v2Fitter.Fitter.DataReader import DataReader
from v2Fitter.Fitter.ObjProvider import ObjProvider
from BsToPhiMuMuFitter.varCollection import dataArgs, Bmass, CosThetaL, CosThetaK, Phimass, dataArgsGEN
from BsToPhiMuMuFitter.anaSetup import q2bins, bMassRegions, cuts, cuts_noResVeto,  modulePath, baseSel
from python.datainput import sigMC, dataFilePath, UnfilteredMC
import ROOT
from ROOT import TChain
from ROOT import TEfficiency, TH2D
from ROOT import RooArgList
from ROOT import RooDataHist

from BsToPhiMuMuFitter.StdProcess import p

CFG = DataReader.templateConfig()
CFG.update({
    'argset': dataArgs,
    'lumi': -1,  # Keep a record, useful for mixing simulations samples
    #'ifriendIndex': ["Bmass", "Mumumass"],
})

# dataReader
def customizeOne(self, targetBMassRegion=None, extraCuts=None):
    print("""Define datasets with arguments.""")
    if self.process.name=="sigMCValidationProcess" and self.name=="sigMCReader":
        sigMCReader.name="sigMCValidation"; sigMCReader.cfg['name']="sigMCValidation"
    if targetBMassRegion is None:
        targetBMassRegion = []
    if not self.process.cfg['binKey'] in q2bins.keys():
        self.logger.logERROR("Bin {0} is not defined.\n".format(self.process.cfg['binKey']))
        raise ValueError

    # With shallow copied CFG, have to bind cfg['dataset'] to a new object.
    self.cfg['dataset'] = []
    for key, val in bMassRegions.items():
        if any([re.match(pat, key) for pat in targetBMassRegion]):
            self.cfg['dataset'].append(
                (
                    "{0}.{1}".format(self.cfg['name'], key),
                    "({0}) && ({1}) && ({2}) && ({3}) && ({4})".format(
                        val['cutString'],
                        "1" if self.process.name=="sigMCValidationProcess" else q2bins[self.process.cfg['binKey']]['cutString'],
                        cuts[-1] if self.process.cfg['binKey'] not in ['jpsi', 'psi2s'] else cuts_noResVeto,
                        "1" if not extraCuts else extraCuts,
                        baseSel,
                    )
                )
            )
    
    # Customize preload TFile
    self.cfg['preloadFile'] = modulePath + "/data/preload_{datasetName}_{binLabel}.root".format(datasetName=self.cfg['name'], binLabel=q2bins[self.process.cfg['binKey']]['label'])

dataReaderCfg = copy(CFG)
dataReaderCfg.update({
    'name': "dataReader",
    'ifile': dataFilePath,
    'preloadFile': modulePath + "/data/preload_dataReader_{binLabel}.root",
    'lumi': 19.98,
})
dataReader = DataReader(dataReaderCfg)
customizeData = functools.partial(customizeOne, targetBMassRegion=['^Fit$', '^SR$', '^.{0,1}SB$'])
dataReader.customize = types.MethodType(customizeData, dataReader)

# sigMCReader
sigMCReaderCfg = copy(CFG)
sigMCReaderCfg.update({
    'name': "sigMCReader",
    'ifile': sigMC,
    'preloadFile': modulePath + "/data/preload_sigMCReader_{binLabel}.root",
    'lumi': 16281.440 + 21097.189,
})
sigMCReader = DataReader(sigMCReaderCfg)
customizeSigMC = functools.partial(customizeOne, targetBMassRegion=['^Fit$'])
sigMCReader.customize = types.MethodType(customizeSigMC, sigMCReader)

# sigMCGENReader
def customizeGEN(self):
    print("""Define datasets with arguments.""")
    if not self.process.cfg['binKey'] in q2bins.keys():
        print("ERROR\t: Bin {0} is not defined.\n".format(self.process.cfg['binKey']))
        raise AttributeError

    # With shallow copied CFG, have to bind cfg['dataset'] to a new object.
    self.cfg['dataset'] = []
    self.cfg['dataset'].append(
        (
            "{0}.Fit".format(self.cfg['name']),
            re.sub("Mumumass", "sqrt(genQ2)", q2bins[self.process.cfg['binKey']]['cutString'])
        )
    )
    # Customize preload TFile
    self.cfg['preloadFile'] = modulePath + "/data/preload_{datasetName}_{binLabel}.root".format(datasetName=self.cfg['name'], binLabel=q2bins[self.process.cfg['binKey']]['label'])

sigMCGENReaderCfg = copy(CFG)
sigMCGENReaderCfg.update({
    'name': "sigMCGENReader",
    'ifile': UnfilteredMC,
    'preloadFile': modulePath + "/data/preload_sigMCGENReader_{binLabel}.root",
    'argset': dataArgsGEN,
})
sigMCGENReader = DataReader(sigMCGENReaderCfg)
sigMCGENReader.customize = types.MethodType(customizeGEN, sigMCGENReader)

# effiHistReader
accXEffThetaLBins = array('d', [-1., -0.8, -0.6, -0.4, -0.2, 0., 0.2, 0.4, 0.6, 0.8, 1.])
accXEffThetaKBins = array('d', [-1., -0.8, -0.6, -0.4, -0.2, 0., 0.2, 0.4, 0.6, 0.8, 1.])
#accXEffThetaLBins = array('d', [-1, -0.7, -0.3, 0., 0.3, 0.7, 1.])
#accXEffThetaKBins = array('d', [-1, -0.7, 0., 0.4, 0.8, 1.])
def buildTotalEffiHist(self):
    """Build efficiency histogram for later fitting/plotting"""
    print("Now I am Here in buildAccXRecEffiHist")
    fin = self.process.filemanager.open("buildAccXRecEffiHist", modulePath + "/data/accXrecEffHists_Run2016.root", "UPDATE")

    # Build acceptance, reco efficiency, and accXrec
    forceRebuild = False
    for binKey in q2bins.keys():
        print q2bins.keys()
        if binKey in ['jpsi', 'psi2s', 'peaks']:
            continue
        h2_accXrec = fin.Get("h2_accXrec1_{0}".format(binKey))
        if h2_accXrec == None or forceRebuild:
            print "\n\n", binKey, "\n\n"
            #h2_acc = fin.Get("h2_acc_{0}".format(binKey))
            #h2_rec = fin.Get("h2_rec_{0}".format(binKey))
            h2_accXrec=fin.Get("h2_accXrec1_{0}".format(binKey)) #Total Eff

            # Fill histograms
            setupEfficiencyBuildProcedure = {}
            setupEfficiencyBuildProcedure['acc'] = {
                'ifiles': UnfilteredMC,
                'baseString': re.sub("Mumumass", "sqrt(genQ2)", q2bins[binKey]['cutString']),
                'cutString': "fabs(genMupEta)<2.2 && fabs(genMumEta)<2.2 && genMupPt>3.9 && genMumPt>3.9", # && KpPt>0.5 && KmPt>0.5 && fabs(KpEta)<2.4 && fabs(KmEta)<2.4",
                'fillXY': "genCosThetaK:genCosThetaL"  # Y:X
            }
            setupEfficiencyBuildProcedure['rec'] = {
                'ifiles': sigMCReader.cfg['ifile'],
                'baseString': re.sub("Mumumass", "sqrt(Q2)", q2bins[binKey]['cutString']),
                'cutString': "({0}) && ({1}) && (Bmass > 4.7) && ({2})".format(cuts[-1], re.sub("Mumumass", "sqrt(Q2)", q2bins[binKey]['cutString']), baseSel),
                'fillXY': "CosThetaK:CosThetaL"  # Y:X
            }
            i=0 #testing events
            h2=h2_accXrec; label='accXrec'  #, label in ((h2_accXrec, 'accXrec')):
            if h2 == None or forceRebuild:
                print("h2: ", h2, label)
                print "BaseSTring: ", setupEfficiencyBuildProcedure['acc']['baseString']
                print "CutString: ", setupEfficiencyBuildProcedure["rec"]['cutString']

                treein = TChain() #flie=ROOT.TFile.Open(f); #treein.SetName(flie.GetListOfKeys().At(0).GetName())
                for f in setupEfficiencyBuildProcedure['acc']['ifiles']:
                    treein.Add(f);   print(f)
                treein.Draw(">>totEvtList", setupEfficiencyBuildProcedure['acc']['baseString'])
                totEvtList = ROOT.gDirectory.Get("totEvtList"); totEvtList.Print() #Pritam

                treeinPassed = TChain()
                for f in setupEfficiencyBuildProcedure['rec']['ifiles']:
                    treeinPassed.Add(f);    print(f)
                treeinPassed.Draw(">>accEvtList", setupEfficiencyBuildProcedure['rec']['cutString'])
                accEvtList = ROOT.gDirectory.Get("accEvtList"); accEvtList.Print()

                h2_total = TH2D("h2_{0}_{1}_total".format(label, binKey), "", len(accXEffThetaLBins) - 1, accXEffThetaLBins, len(accXEffThetaKBins) - 1, accXEffThetaKBins)
                h2_passed = h2_total.Clone("h2_{0}_{1}_passed".format(label, binKey))

                h2_fine_total = TH2D("h2_{0}_fine_{1}_total".format(label, binKey), "", 20, -1, 1, 20, -1, 1)
                h2_fine_passed = h2_fine_total.Clone("h2_{0}_fine_{1}_passed".format(label, binKey))

                treein.SetEventList(totEvtList)
                for hist in h2_total, h2_fine_total:
                    treein.Draw("{0}>>{1}".format(setupEfficiencyBuildProcedure['acc']['fillXY'], hist.GetName()), "", "goff")

                treeinPassed.SetEventList(accEvtList)
                for hist in h2_passed, h2_fine_passed:
                    treeinPassed.Draw("{0}>>{1}".format(setupEfficiencyBuildProcedure['rec']['fillXY'], hist.GetName()), "", "goff")

                h2_eff = TEfficiency(h2_passed, h2_total)
                h2_eff_fine = TEfficiency(h2_fine_passed, h2_fine_total)

                fin.cd()
                for proj, var in [("ProjectionX", CosThetaL), ("ProjectionY", CosThetaK)]:
                    proj_fine_total = getattr(h2_fine_total, proj)("{0}_{1}".format(h2_fine_total.GetName(), proj), 0, -1, "e")
                    proj_fine_passed = getattr(h2_fine_passed, proj)("{0}_{1}".format(h2_fine_passed.GetName(), proj), 0, -1, "e")
                    h_eff = TEfficiency(proj_fine_passed, proj_fine_total)
                    h_eff.Write("h_{0}_fine_{1}_{2}".format(label, binKey, proj), ROOT.TObject.kOverwrite)

                h2_eff.Write("h2Eff_{0}_{1}".format(label, binKey), ROOT.TObject.kOverwrite)           #Binned 2D Eff
                h2_eff_fine.Write("h2_{0}_fine_{1}".format(label, binKey), ROOT.TObject.kOverwrite) #2D Efficiency Total 

            # : Converting TEff to TH1D
            fin.cd()
            for proj in ["ProjectionX", "ProjectionY"]:
                #h_acc_fine = fin.Get("h_acc_fine_{0}_{1}".format(binKey, proj))
                #h_rec_fine = fin.Get("h_rec_fine_{0}_{1}".format(binKey, proj))
                h_accXrec_fineEff = fin.Get("h_accXrec_fine_{0}_{1}".format(binKey, proj))
                h_accXrec_fine = h_accXrec_fineEff.GetPassedHistogram().Clone("h_accXrec_fine_{0}_{1}".format(binKey, proj))
                h_accXrec_fine.Reset("ICESM")
                for b in range(1, h_accXrec_fine.GetNbinsX() + 1):
                    h_accXrec_fine.SetBinContent(b, h_accXrec_fineEff.GetEfficiency(b))
                    h_accXrec_fine.SetBinError(b, h_accXrec_fine.GetBinContent(b) * math.sqrt(1 / h_accXrec_fineEff.GetTotalHistogram().GetBinContent(b) + 1 / h_accXrec_fineEff.GetPassedHistogram().GetBinContent(b)))
                h_accXrec_fine.Write("h_accXrec_{0}_{1}".format(binKey, proj), ROOT.TObject.kOverwrite)

            #h2_acc = fin.Get("h2_acc_{0}".format(binKey))
            #h2_rec = fin.Get("h2_rec_{0}".format(binKey))
            h2_accXrecEff1 = fin.Get("h2Eff_accXrec_{0}".format(binKey))        #2D Binned Eff
            h2_accXrec1 = h2_accXrecEff1.GetPassedHistogram().Clone("h2_accXrec1_{0}".format(binKey)); print "Before Converting: ", type(h2_accXrecEff1), type(h2_accXrec1)
            h2_accXrec1.Reset("ICESM")
            for iL, iK in itertools.product(range(1, len(accXEffThetaLBins)), range(1, len(accXEffThetaKBins))):
                if h2_accXrecEff1.GetTotalHistogram().GetBinContent(iL, iK) == 0:
                    h2_accXrec1.SetBinContent(iL, iK, 0)
                    h2_accXrec1.SetBinError(iL, iK, 1)
                else:
                    iLK = h2_accXrecEff1.GetGlobalBin(iL, iK)
                    h2_accXrec1.SetBinContent(iL, iK, h2_accXrecEff1.GetEfficiency(iLK))
                    h2_accXrec1.SetBinError(iL, iK, h2_accXrec1.GetBinContent(iL, iK) * math.sqrt(1. / h2_accXrecEff1.GetTotalHistogram().GetBinContent(iLK) + 1. / h2_accXrecEff1.GetPassedHistogram().GetBinContent(iLK)))
            h2_accXrec1.SetXTitle("cos#theta_{l}")
            h2_accXrec1.SetYTitle("cos#theta_{K}")
            h2_accXrec1.SetZTitle("Overall efficiency")
            h2_accXrec1.Write("h2_accXrec1_{0}".format(binKey), ROOT.TObject.kOverwrite)
            self.logger.logINFO("Overall efficiency is built.")

            h2_accXrecEff = fin.Get("h2Eff_accXrec_{0}".format(binKey))        #2D Binned Eff: Same as h2_accXrec1_binKey, but using CreateHistogram()
            h2_accXrec = h2_accXrecEff.CreateHistogram(); h2_accXrec.SetTitle("Created from CreateHistogram() method")
            h2_accXrec.SetXTitle("cos#theta_{l}")
            h2_accXrec.SetYTitle("cos#theta_{K}")
            h2_accXrec.SetZTitle("Overall efficiency")
            h2_accXrec.Write("h2_accXrec_{0}".format(binKey), ROOT.TObject.kOverwrite)  # We are not going to use this as of now
            self.logger.logINFO("Overall efficiency is built.")

    # Register the chosen one to sourcemanager
    h2_accXrec = fin.Get("h2_accXrec1_{0}".format(self.process.cfg['binKey'])); print "Getting From File: ", type(h2_accXrec), "h2_accXrec1_{0}".format(self.process.cfg['binKey'])
    self.cfg['source']['effiHistReader.h2_accXrec'] = h2_accXrec
    self.cfg['source']['effiHistReader.accXrec'] = RooDataHist("accXrec", "", RooArgList(CosThetaL, CosThetaK), ROOT.RooFit.Import(h2_accXrec)) # Effi 2D RooDataHist
    self.cfg['source']['effiHistReader.h_accXrec_fine_ProjectionX'] = fin.Get("h_accXrec_{0}_ProjectionX".format(self.process.cfg['binKey'])) #Effi of CosThetaL
    self.cfg['source']['effiHistReader.h_accXrec_fine_ProjectionY'] = fin.Get("h_accXrec_{0}_ProjectionY".format(self.process.cfg['binKey'])) # Effi of CosThetaK


def buildAccXRecEffiHist(self):
    """Build efficiency histogram for later fitting/plotting"""
    targetBins = ['belowJpsiA', 'belowJpsiB', 'belowJpsiC', 'betweenPeaks', 'abovePsi2sA', 'abovePsi2sB', 'summary', 'summaryLowQ2']
    if self.process.cfg['binKey'] not in targetBins:
        return

    fin = self.process.filemanager.open("buildAccXRecEffiHist", modulePath + "/data/accXrecEffHists_Run2012.root", "UPDATE")
    #pdb.set_trace()
    # Build acceptance, reco efficiency, and accXrec
    forceRebuild = False

    binKey = self.process.cfg['binKey']
    h2_accXrec = fin.Get("h2_accXrec_{0}".format(binKey))
    if h2_accXrec == None or forceRebuild:
        h2_acc = fin.Get("h2_acc_{0}".format(binKey))
        h2_rec = fin.Get("h2_rec_{0}".format(binKey))

        # Fill histograms
        setupEfficiencyBuildProcedure = {}
        setupEfficiencyBuildProcedure['acc'] = {
            'ifiles': [] if binKey in ['jpsi', 'psi2s'] else UnfilteredMC,
            'baseString': re.sub("Mumumass", "sqrt(genQ2)", q2bins[binKey]['cutString']),
            'cutString': "({0}) && fabs(genMupEta)<2.2 && fabs(genMumEta)<2.2 && genMupPt>4.0 && genMumPt>4.0".format(re.sub("Mumumass", "sqrt(genQ2)", q2bins[binKey]['cutString'])),
            'fillXY': "genCosThetaK:genCosThetaL",  # Y:X
            'weight': None
        }
        setupEfficiencyBuildProcedure['rec'] = {
            'ifiles': sigMCReader.cfg['ifile'],
            'baseString': "({0}) && ({1})".format(re.sub("Mumumass", "sqrt(Q2)", q2bins[binKey]['cutString']), baseSel), #"{0}".format(setupEfficiencyBuildProcedure['acc']['baseString']),
            'cutString': "(Bmass > 4.7) && ({0}) && ({1}) && ({2})".format(cuts_antiResVeto if binKey in ['jpsi', 'psi2s'] else cuts[-1], re.sub("Mumumass", "sqrt(Q2)", q2bins[binKey]['cutString']), baseSel),
            'fillXY': "CosThetaK:CosThetaL",  # Y:X
            'weight': None
        }
        for h2, label in (h2_acc, 'acc'), (h2_rec, 'rec'):
            if h2 == None or forceRebuild:
                treein = TChain("tree")
                for f in setupEfficiencyBuildProcedure[label]['ifiles']:
                    treein.Add(f)

                if setupEfficiencyBuildProcedure[label]['weight'] is None:
                    df_tot = ROOT.RDataFrame(treein).Define('weight', "1").Filter(setupEfficiencyBuildProcedure[label]['baseString'])
                else:
                    df_tot = ROOT.RDataFrame(treein).Define('weight', *setupEfficiencyBuildProcedure[label]['weight']).Filter(setupEfficiencyBuildProcedure[label]['baseString'])
                df_acc = df_tot.Filter(setupEfficiencyBuildProcedure[label]['cutString'])

                fillXY = setupEfficiencyBuildProcedure[label]['fillXY'].split(':')
                h2_total_config = ("h2_{0}_{1}_total".format(label, binKey), "", len(accXEffThetaLBins) - 1, accXEffThetaLBins, len(accXEffThetaKBins) - 1, accXEffThetaKBins)
                h2_passed_config  = ("h2_{0}_{1}_passed".format(label, binKey), "", len(accXEffThetaLBins) - 1, accXEffThetaLBins, len(accXEffThetaKBins) - 1, accXEffThetaKBins)
                h2_fine_total_config = ("h2_{0}_fine_{1}_total".format(label, binKey), "", 10, -1, 1, 10, -1, 1)
                h2_fine_passed_config = ("h2_{0}_fine_{1}_passed".format(label, binKey), "", 10, -1, 1, 10, -1, 1)

                h2ptr_total = df_tot.Histo2D(h2_total_config, fillXY[1], fillXY[0], "weight")
                h2ptr_passed = df_acc.Histo2D(h2_passed_config, fillXY[1], fillXY[0], "weight")
                h2ptr_fine_total = df_tot.Histo2D(h2_fine_total_config, fillXY[1], fillXY[0], "weight")
                h2ptr_fine_passed = df_acc.Histo2D(h2_fine_passed_config, fillXY[1], fillXY[0], "weight")

                h2_total = h2ptr_total.GetValue()
                h2_passed = h2ptr_passed.GetValue()
                h2_fine_total = h2ptr_fine_total.GetValue()
                h2_fine_passed = h2ptr_fine_passed.GetValue()

                print("{0}/{1}".format(df_acc.Count().GetValue(), df_tot.Count().GetValue()))
                h2_eff = TEfficiency(h2_passed, h2_total)
                h2_eff_fine = TEfficiency(h2_fine_passed, h2_fine_total)

                #pdb.set_trace()
                fin.cd()
                for proj, var in [("ProjectionX", CosThetaL), ("ProjectionY", CosThetaK)]:
                    proj_fine_total = getattr(h2_fine_total, proj)("{0}_{1}".format(h2_fine_total.GetName(), proj), 0, -1, "e")
                    proj_fine_passed = getattr(h2_fine_passed, proj)("{0}_{1}".format(h2_fine_passed.GetName(), proj), 0, -1, "e")
                    h_eff = TEfficiency(proj_fine_passed, proj_fine_total)
                    h_eff.Write("h_{0}_fine_{1}_{2}".format(label, binKey, proj), ROOT.TObject.kOverwrite)

                h2_eff.Write("h2_{0}_{1}".format(label, binKey), ROOT.TObject.kOverwrite)
                h2_eff_fine.Write("h2_{0}_fine_{1}".format(label, binKey), ROOT.TObject.kOverwrite)

                del df_acc, df_tot

        #pdb.set_trace()
        # Merge acc and rec to accXrec
        fin.cd()
        for proj in ["ProjectionX", "ProjectionY"]:
            h_acc_fine = fin.Get("h_acc_fine_{0}_{1}".format(binKey, proj))
            h_rec_fine = fin.Get("h_rec_fine_{0}_{1}".format(binKey, proj))
            h_accXrec_fine = h_acc_fine.GetPassedHistogram().Clone("h_accXrec_fine_{0}_{1}".format(binKey, proj))
            h_accXrec_fine.Reset("ICESM")
            for b in range(1, h_accXrec_fine.GetNbinsX() + 1):
                if h_rec_fine.GetTotalHistogram().GetBinContent(b) == 0 or h_rec_fine.GetPassedHistogram().GetBinContent(b) == 0:
                    h_accXrec_fine.SetBinContent(b, 0)
                    h_accXrec_fine.SetBinError(b, 1)
                    print ">> Empty reco eff bin #", b
                else:
                    h_accXrec_fine.SetBinContent(b, h_acc_fine.GetEfficiency(b) * h_rec_fine.GetEfficiency(b))
                    h_accXrec_fine.SetBinError(b, h_accXrec_fine.GetBinContent(b) * math.sqrt(1 / h_acc_fine.GetTotalHistogram().GetBinContent(b) + 1 / h_acc_fine.GetPassedHistogram().GetBinContent(b) + 1 / h_rec_fine.GetTotalHistogram().GetBinContent(b) + 1 / h_rec_fine.GetPassedHistogram().GetBinContent(b)))
            h_accXrec_fine.Write("h_accXrec_{0}_{1}".format(binKey, proj), ROOT.TObject.kOverwrite)

        h2_acc = fin.Get("h2_acc_{0}".format(binKey))
        h2_rec = fin.Get("h2_rec_{0}".format(binKey))
        h2_accXrec = h2_acc.GetPassedHistogram().Clone("h2_accXrec_{0}".format(binKey))
        h2_accXrec.Reset("ICESM")
        for iL, iK in itertools.product(range(1, len(accXEffThetaLBins)), range(1, len(accXEffThetaKBins))):
            if h2_rec.GetTotalHistogram().GetBinContent(iL, iK) == 0 or h2_rec.GetPassedHistogram().GetBinContent(iL, iK) == 0 or h2_acc.GetTotalHistogram().GetBinContent(iL, iK) == 0 or h2_acc.GetPassedHistogram().GetBinContent(iL, iK) == 0:
                h2_accXrec.SetBinContent(iL, iK, 0)
                h2_accXrec.SetBinError(iL, iK, 1)
                print ">> Empty recoORacc eff bin #", iL, iK
            else:
                iLK = h2_acc.GetGlobalBin(iL, iK)
                h2_accXrec.SetBinContent(iL, iK, h2_acc.GetEfficiency(iLK) * h2_rec.GetEfficiency(iLK))
                h2_accXrec.SetBinError(iL, iK, h2_accXrec.GetBinContent(iL, iK) * math.sqrt(1 / h2_acc.GetTotalHistogram().GetBinContent(iLK) + 1 / h2_acc.GetPassedHistogram().GetBinContent(iLK) + 1 / h2_rec.GetTotalHistogram().GetBinContent(iLK) + 1 / h2_rec.GetPassedHistogram().GetBinContent(iLK)))
        h2_accXrec.SetXTitle("cos#theta_{l}")
        h2_accXrec.SetYTitle("cos#theta_{K}")
        h2_accXrec.SetZTitle("Overall efficiency")

        h2_accXrec.Write("h2_accXrec_{0}".format(binKey), ROOT.TObject.kOverwrite)
        self.logger.logINFO("Overall efficiency is built.")

    # Register the chosen one to sourcemanager
    #  h2_accXrec = fin.Get("h2_accXrec_{0}".format(self.process.cfg['binKey']))
    self.cfg['source'][self.name + '.h2_accXrec'] = h2_accXrec
    self.cfg['source'][self.name + '.accXrec'] = RooDataHist("accXrec", "", RooArgList(CosThetaL, CosThetaK), ROOT.RooFit.Import(h2_accXrec))
    self.cfg['source'][self.name + '.h_accXrec_fine_ProjectionX'] = fin.Get("h_accXrec_{0}_ProjectionX".format(self.process.cfg['binKey']))
    self.cfg['source'][self.name + '.h_accXrec_fine_ProjectionY'] = fin.Get("h_accXrec_{0}_ProjectionY".format(self.process.cfg['binKey']))

effiHistReaderOneStep = ObjProvider({
    'name': "effiHistReaderOneStep",
    'obj': {
        'effiHistReaderOneStep.h2_accXrec': [buildTotalEffiHist, ],
    }
})

effiHistReader = ObjProvider({
    'name': "effiHistReader",
    'obj': {
        'effiHistReader.h2_accXrec': [buildAccXRecEffiHist, ],
    }
})

if __name__ == '__main__':
    # p.setSequence([dataReader])
    # p.setSequence([sigMCReader])
    p.setSequence([effiHistReader])
    p.beginSeq()
    p.runSeq()
    p.endSeq()
