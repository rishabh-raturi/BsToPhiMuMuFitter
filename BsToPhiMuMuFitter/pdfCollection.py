#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: set sw=4 ts=4 fdm=indent fdn=3 ft=python et:

# Description     : Define PDFs
# Author          : Po-Hsun Chen (pohsun.chen.hep@gmail.com)
#                   Pritam Kalbhor (physics.pritam@gmail.com)
# Last Modified   : 19 Apr 2020 12:04 01:26

############
# WARNINGS #
############
# Dont call TObject.Print(), it seems the iterators leads to random crash
# In RooWorkspace.factory(), you MUST replace the calculation between numbers to a single float number, e.g. 2/3 -> 0.666667
#   It is possible that the parser don't designed to handle RooAddition and RooProduct between RooConstVar

import types, sys, pdb
import functools
from copy import copy, deepcopy
from collections import OrderedDict

from v2Fitter.Fitter.ObjProvider import ObjProvider
from v2Fitter.Fitter.WspaceReader import WspaceReader

from BsToPhiMuMuFitter.StdProcess import isDEBUG
from BsToPhiMuMuFitter.anaSetup import modulePath, q2bins
from BsToPhiMuMuFitter.varCollection import Bmass, CosThetaK, CosThetaL
import BsToPhiMuMuFitter.cpp
import BsToPhiMuMuFitter.dataCollection as dataCollection

import ROOT
from ROOT import RooWorkspace
from ROOT import RooEffProd
from ROOT import RooKeysPdf

from BsToPhiMuMuFitter.StdProcess import p

def getWspace(self):
    """Read workspace"""
    wspaceName = "wspace.{0}".format(self.cfg.get('wspaceTag', "DEFAULT"))
    if wspaceName in self.process.sourcemanager.keys():
        wspace = self.process.sourcemanager.get(wspaceName)
    else:
        if not isDEBUG:
            self.logger.logERROR("RooWorkspace '{0}' not found".format(wspaceName))
            self.logger.logDEBUG("Please access RooWorkspace with WspaceReader")
            raise RuntimeError
        wspace = RooWorkspace(wspaceName)
        self.process.sourcemanager.update(wspaceName, wspace)
    wspace.addClassDeclImportDir(modulePath) #+ '/cpp')
    wspace.addClassImplImportDir(modulePath) #+ '/cpp')
    return wspace


ObjProvider.getWspace = types.MethodType(getWspace, None, ObjProvider)

#########################
# Now start define PDFs #
#########################


def buildGenericObj(self, objName, factoryCmd, varNames):
    """Build with RooWorkspace.factory. See also RooFactoryWSTool.factory"""
    wspace = self.getWspace()
    # print("WSPACE: ", wspace.Print())
    obj = wspace.obj(objName)
    if obj == None:
        # print("objName: ", objName)
        self.logger.logINFO("Build {0} from scratch.".format(objName))
        for v in varNames:
            if wspace.obj(v) == None:
                getattr(wspace, 'import')(globals()[v])  #Import CosThetaK and CosThetaL 
        for cmdIdx, cmd in enumerate(factoryCmd):
            wspace.factory(cmd)
        obj = wspace.obj(objName)
        print("OBJ: ", obj)
    self.cfg['source'][objName] = obj

f_effiSigA_format = {}

pdfL = "1+l1*CosThetaL+l2*pow(CosThetaL,2)+l3*pow(CosThetaL,3)+l4*pow(CosThetaL,4)+l5*pow(CosThetaL,5)+l6*pow(CosThetaL,6)+l7*pow(CosThetaL,7)"; nLo=8
pdfK = "1+k1*CosThetaK+k2*pow(CosThetaK,2)+k3*pow(CosThetaK,3)+k4*pow(CosThetaK,4)+k5*pow(CosThetaK,5)+k6*pow(CosThetaK,6)+k7*pow(CosThetaK,7)"; nK=8
n=25 #Number of x. LP4*Pol4
xTerm = "\
(x0+x1*CosThetaK+x2*(1.5*pow(CosThetaK,2)-0.5)+x3*(2.5*pow(CosThetaK,3)-1.5*CosThetaK)+x4*(4.375*pow(CosThetaK, 4)-3.75*pow(CosThetaK, 2)+0.375))\
+(x5+x6*CosThetaK+x7*(1.5*pow(CosThetaK,2)-0.5)+x8*(2.5*pow(CosThetaK,3)-1.5*CosThetaK)+x9*(4.375*pow(CosThetaK, 4)-3.75*pow(CosThetaK, 2)+0.375))*CosThetaL\
+(x10+x11*CosThetaK+x12*(1.5*pow(CosThetaK,2)-0.5)+x13*(2.5*pow(CosThetaK,3)-1.5*CosThetaK)+x14*(4.375*pow(CosThetaK, 4)-3.75*pow(CosThetaK, 2)+0.375))*pow(CosThetaL,2)\
+(x15+x16*CosThetaK+x17*(1.5*pow(CosThetaK,2)-0.5)+x18*(2.5*pow(CosThetaK,3)-1.5*CosThetaK)+x19*(4.375*pow(CosThetaK, 4)-3.75*pow(CosThetaK, 2)+0.375))*pow(CosThetaL,3)\
+(x20+x21*CosThetaK+x22*(1.5*pow(CosThetaK,2)-0.5)+x23*(2.5*pow(CosThetaK,3)-1.5*CosThetaK)+x24*(4.375*pow(CosThetaK, 4)-3.75*pow(CosThetaK, 2)+0.375))*pow(CosThetaL,4)"

f_effiSigA_format['DEFAULT'] = ["l{0}[-10,10]".format(i) for i in range(1, nLo)] \
    + ["k{0}[-10,10]".format(i) for i in range(1, nK)] \
    + ["effi_norm[0,1]", "hasXTerm[0]"] + ["x{0}[-2,2]".format(i) for i in range(n)] \
    + ["EXPR::effi_cosl('{pdf}',{args})".format(pdf=pdfL, args="{CosThetaL, " + ', '.join(["l{0}".format(i) for i in range(1, nLo)]) + "}")] \
    + ["EXPR::effi_cosK('{pdf}',{args})".format(pdf=pdfK, args="{CosThetaK, " + ', '.join(["k{0}".format(i) for i in range(1, nK)]) + "}")] \
    + ["expr::effi_xTerm('1+hasXTerm*({xTerm})',{args})".format(xTerm=xTerm, args="{CosThetaL,CosThetaK,hasXTerm," + ','.join(["x{0}".format(i) for i in range(n)]) + "}")] \
    + ["expr::effi_sigA('effi_norm*({pdfL})*({pdfK})*(1+hasXTerm*({xTerm}))', {args})".format(
        pdfL=pdfL,
        pdfK=pdfK,
        xTerm=xTerm,
        args="{CosThetaL,CosThetaK,hasXTerm,effi_norm," + ','.join(["l{0}".format(i) for i in range(1, nLo)] + ["k{0}".format(i) for i in range(1, nK)] + ["x{0}".format(i) for i in range(n)]) + "}")]

pdfL = "l1*exp(-0.5*pow((CosThetaL-l2)/l3,2))+l4*exp(-0.5*pow((CosThetaL-l5)/l6,2))+l7*exp(-0.5*pow((CosThetaL-l8)/l9,2))"; nLc=9
f_effiSigA_format['belowJpsiA'] = ["l{0}[.1,0,10]".format(3*i-2) for i in range(1, nLc/3+1)] \
    + ["l{0}[0,-.5,.5]".format(3*i-1) for i in range(1, nLc/3+1)] \
    + ["l{0}[.2,.1,2.]".format(3*i) for i in range(1, nLc/3+1)] \
    + ["k{0}[-10,10]".format(i) for i in range(1, nK)] \
    + ["effi_norm[0,1]", "hasXTerm[0]"] + ["x{0}[-2,2]".format(i) for i in range(n)] \
    + ["EXPR::effi_cosl('{pdf}',{args})".format(pdf=pdfL, args="{CosThetaL," + ', '.join(["l{0}".format(i) for i in range(1, nLc+1)]) + "}")] \
    + ["EXPR::effi_cosK('{pdf}',{args})".format(pdf=pdfK, args="{CosThetaK," + ', '.join(["k{0}".format(i) for i in range(1, nK)]) + "}")] \
    + ["expr::effi_xTerm('1+hasXTerm*({xTerm})',{args})".format(xTerm=xTerm, args="{CosThetaL,CosThetaK,hasXTerm," + ','.join(["x{0}".format(i) for i in range(n)]) + "}")] \
    + ["expr::effi_sigA('effi_norm*({pdfL})*({pdfK})*(1+hasXTerm*({xTerm}))', {args})".format(
        pdfL=pdfL,
        pdfK=pdfK,
        xTerm=xTerm,
        args="{CosThetaL,CosThetaK,hasXTerm,effi_norm," + ','.join(["l{0}".format(i) for i in range(1, nLc+1)] + ["k{0}".format(i) for i in range(1, nK)] + ["x{0}".format(i) for i in range(n)]) + "}")]

#f_effiSigA_format['belowJpsiC'] = deepcopy(f_effiSigA_format['belowJpsiA'])
#f_effiSigA_format['summaryLowQ2'] = deepcopy(f_effiSigA_format['belowJpsiA'])
pdfL = "l1*exp(-0.5*pow((CosThetaL-l2)/l3,2))+l4*exp(-0.5*pow((CosThetaL-l5)/l6,2))+l7*exp(-0.5*pow((CosThetaL-l8)/l9,2))"; nLB=9
f_effiSigA_format['belowJpsiB'] = ["l{0}[.1,0,10]".format(3*i-2) for i in range(1, nLB/3+1)] \
    + ["l{0}[0,-.5,.5]".format(3*i-1) for i in range(1, nLB/3+1)] \
    + ["l{0}[.2,.1,2.]".format(3*i) for i in range(1, nLB/3+1)] \
    + ["k{0}[-10,10]".format(i) for i in range(1, nK)] \
    + ["effi_norm[0,1]", "hasXTerm[0]"] + ["x{0}[-2,2]".format(i) for i in range(n)] \
    + ["EXPR::effi_cosl('{pdf}',{args})".format(pdf=pdfL, args="{CosThetaL," + ', '.join(["l{0}".format(i) for i in range(1, nLB+1)]) + "}")] \
    + ["EXPR::effi_cosK('{pdf}',{args})".format(pdf=pdfK, args="{CosThetaK," + ', '.join(["k{0}".format(i) for i in range(1, nK)]) + "}")] \
    + ["expr::effi_xTerm('1+hasXTerm*({xTerm})',{args})".format(xTerm=xTerm, args="{CosThetaL,CosThetaK,hasXTerm," + ','.join(["x{0}".format(i) for i in range(n)]) + "}")] \
    + ["expr::effi_sigA('effi_norm*({pdfL})*({pdfK})*(1+hasXTerm*({xTerm}))', {args})".format(
        pdfL=pdfL,
        pdfK=pdfK,
        xTerm=xTerm,
        args="{CosThetaL,CosThetaK,hasXTerm,effi_norm," + ','.join(["l{0}".format(i) for i in range(1, nLB+1)] + ["k{0}".format(i) for i in range(1, nK)] + ["x{0}".format(i) for i in range(n)]) + "}")]


pdfL = "l1*exp(-0.5*pow((CosThetaL-l2)/l3,2))+l4*exp(-0.5*pow((CosThetaL-l5)/l6,2))+l7*exp(-0.5*pow((CosThetaL-l8)/l9,2))"; nLB=9
f_effiSigA_format['summaryLowQ2'] = ["l{0}[.1,0,10]".format(3*i-2) for i in range(1, nLB/3+1)] \
    + ["l{0}[0,-.5,.5]".format(3*i-1) for i in range(1, nLB/3+1)] \
    + ["l{0}[.2,.1,2.]".format(3*i) for i in range(1, nLB/3+1)] \
    + ["k{0}[-10,10]".format(i) for i in range(1, nK)] \
    + ["effi_norm[0,1]", "hasXTerm[0]"] + ["x{0}[-2,2]".format(i) for i in range(n)] \
    + ["EXPR::effi_cosl('{pdf}',{args})".format(pdf=pdfL, args="{CosThetaL," + ', '.join(["l{0}".format(i) for i in range(1, nLB+1)]) + "}")] \
    + ["EXPR::effi_cosK('{pdf}',{args})".format(pdf=pdfK, args="{CosThetaK," + ', '.join(["k{0}".format(i) for i in range(1, nK)]) + "}")] \
    + ["expr::effi_xTerm('1+hasXTerm*({xTerm})',{args})".format(xTerm=xTerm, args="{CosThetaL,CosThetaK,hasXTerm," + ','.join(["x{0}".format(i) for i in range(n)]) + "}")] \
    + ["expr::effi_sigA('effi_norm*({pdfL})*({pdfK})*(1+hasXTerm*({xTerm}))', {args})".format(
        pdfL=pdfL,
        pdfK=pdfK,
        xTerm=xTerm,
        args="{CosThetaL,CosThetaK,hasXTerm,effi_norm," + ','.join(["l{0}".format(i) for i in range(1, nLB+1)] + ["k{0}".format(i) for i in range(1, nK)] + ["x{0}".format(i) for i in range(n)]) + "}")]

setupBuildEffiSigA = {
    'objName': "effi_sigA",
    'varNames': ["CosThetaK", "CosThetaL"],
    'factoryCmd': [
    ]
}

setupBuildSigM = {
    'objName': "f_sigM",
    'varNames': ["Bmass"],
    'factoryCmd': [
        "sigMGauss_mean[5.38, 5.30, 5.5]",
        "RooGaussian::f_sigMGauss1(Bmass, sigMGauss_mean, sigMGauss1_sigma[0.02, 0.0001, 0.05])",
        "RooGaussian::f_sigMGauss2(Bmass, sigMGauss_mean, sigMGauss2_sigma[0.08, 0.0005, 0.40])",
        "SUM::f_sigM(sigM_frac[0.,0.,1.]*f_sigMGauss1, f_sigMGauss2)",
    ],
}
buildSigM = functools.partial(buildGenericObj, **setupBuildSigM)

def buildSigA(self):
    """Build with RooWorkspace.factory. See also RooFactoryWSTool.factory"""
    wspace = self.getWspace()

    f_sigA = wspace.pdf("f_sigA")
    if f_sigA == None:
        # wspace.factory("fs[0.00001,0.00001,0.2]")
        wspace.factory("unboundFl[0.6978,-1e2,1e2]")
        wspace.factory("unboundAfb[-0.0016,-1e2,1e2]")
        # wspace.factory("transAs[0,-1e5,1e5]")
        wspace.factory("expr::fl('0.5+TMath::ATan(unboundFl)/TMath::Pi()',{unboundFl})")
        wspace.factory("expr::afb('2.*(1-fl)*TMath::ATan(unboundAfb)/TMath::Pi()',{unboundAfb,fl})")
        # wspace.factory("expr::as('1.78*TMath::Sqrt(3*fs*(1-fs)*fl)*transAs',{fs,fl,transAs})")
        wspace.factory("EXPR::f_sigA_original('(9.0/16.0)*((0.5*(1.0-fl)*(1.0-CosThetaK*CosThetaK)*(1.0+CosThetaL*CosThetaL)) + (2.0*fl*CosThetaK*CosThetaK*(1.0-CosThetaL*CosThetaL)) + (afb*(1.0-CosThetaK*CosThetaK)*CosThetaL))', {CosThetaK, CosThetaL, fl, afb})")
        f_sigA = ROOT.RooBtosllModel("f_sigA", "", CosThetaL, CosThetaK, wspace.var('unboundAfb'), wspace.var('unboundFl'))
        getattr(wspace, 'import')(f_sigA)
        wspace.importClassCode(ROOT.RooBtosllModel.Class())

    self.cfg['source']['f_sigA'] = f_sigA

def buildSig(self):
    """Build with RooWorkspace.factory. See also RooFactoryWSTool.factory"""
    wspace = self.getWspace()

    f_sig2D = wspace.obj("f_sig2D")
    f_sig3D = wspace.obj("f_sig3D")
    if f_sig3D == None:
        for k in ['effi_sigA', 'f_sigA', 'f_sigM']:
            locals()[k] = self.cfg['source'][k] if k in self.cfg['source'] else self.process.sourcemanager.get(k)
        f_sig2D = RooEffProd("f_sig2D", "", locals()['f_sigA'], locals()['effi_sigA'])
        getattr(wspace, 'import')(f_sig2D, ROOT.RooFit.RecycleConflictNodes())
        if wspace.obj("f_sigM") == None:
            getattr(wspace, 'import')(locals()['f_sigM'])
        wspace.factory("PROD::f_sig3D(f_sigM, f_sig2D)")
        f_sig3D = wspace.pdf("f_sig3D")

    self.cfg['source']['f_sig2D'] = f_sig2D
    self.cfg['source']['f_sig3D'] = f_sig3D

setupBuildBkgCombM = {
    'objName': "f_bkgCombM",
    'varNames': ["Bmass"],
    'factoryCmd': [
        "bkgCombM_c1[-5,-20,0]",
        "EXPR::f_bkgCombM('exp(bkgCombM_c1*Bmass)',{Bmass,bkgCombM_c1})",
    ],
}
buildBkgCombM = functools.partial(buildGenericObj, **setupBuildBkgCombM)

setupBuildBkgCombMAltM = {
    'objName': "f_bkgCombMAltM",
    'varNames': ["Bmass"],
    'factoryCmd': [
        "bkgCombMAltM_c1[0.1,1e-5,10]",
        "bkgCombMAltM_c2[-5.6,-20,-4]",
        "EXPR::f_bkgCombMAltM('bkgCombMAltM_c1+pow(Bmass+bkgCombMAltM_c2,2)',{Bmass,bkgCombMAltM_c1,bkgCombMAltM_c2})",
    ],
}
buildBkgCombMAltM = functools.partial(buildGenericObj, **setupBuildBkgCombMAltM)

f_analyticBkgCombA_format = {}

"""f_analyticBkgCombA_format['belowJpsiA'] = [
    "bkgCombL_c0[0,10]",
    "bkgCombL_c1[0.3,0.9]",
    "bkgCombL_c2[0.2, 0.1, 1.0]",
    "bkgCombL_c3[-0.8,-0.2]",
    "bkgCombL_c4[0.2, 0.1, 1.0]",
    "bkgCombL_c5[0,10]",
    "bkgCombK_c1[ 0,10]",
    "bkgCombK_c2[0,50]",
    "bkgCombK_c3[-3,0]",
    "EXPR::f_bkgCombA('({pdfL})*({pdfK})', {args})".format(
        pdfL="bkgCombL_c0*exp(-0.5*pow((CosThetaL-bkgCombL_c1)/bkgCombL_c2,2))+bkgCombL_c5*exp(-0.5*pow((CosThetaL-bkgCombL_c3)/bkgCombL_c4,2))",
        pdfK="exp(bkgCombK_c1*CosThetaK)+exp(bkgCombK_c3*CosThetaK+bkgCombK_c2)",
        args="{CosThetaL, CosThetaK, bkgCombL_c0, bkgCombL_c1, bkgCombL_c2, bkgCombL_c3, bkgCombL_c4, bkgCombL_c5, bkgCombK_c1, bkgCombK_c2, bkgCombK_c3}")
]"""

f_analyticBkgCombA_format['belowJpsiA'] = [
    "bkgCombL_c1[-10,10]",
    "bkgCombL_c2[-10,10]",
    "bkgCombL_c3[-10,10]",
    "bkgCombL_c4[-10,10]",
    "bkgCombK_c1[ 0,10]",
    "bkgCombK_c2[0,50]",
    "bkgCombK_c3[-3,0]",
    "EXPR::f_bkgCombA('({pdfL})*({pdfK})', {args})".format(
        pdfL="1+bkgCombL_c1*CosThetaL+bkgCombL_c2*pow(CosThetaL, 2)+bkgCombL_c3*pow(CosThetaL,3) + bkgCombL_c4*pow(CosThetaL,4)",
        pdfK="exp(bkgCombK_c1*CosThetaK)+exp(bkgCombK_c3*CosThetaK+bkgCombK_c2)",
        args="{CosThetaL, CosThetaK, bkgCombL_c1, bkgCombL_c2, bkgCombL_c3, bkgCombL_c4, bkgCombK_c1, bkgCombK_c2, bkgCombK_c3}")
]
f_analyticBkgCombA_format['betweenPeaks'] = [
    "bkgCombL_c1[-3,3]",
    "bkgCombL_c2[0.1, 0.01, 0.5]",
    "bkgCombL_c3[-3,3]",
    "bkgCombL_c4[0.1, 0.01, 1.0]",
    "bkgCombL_c5[0,10]",
    "bkgCombK_c1[-10,10]",
    "bkgCombK_c2[-10,10]",
    "bkgCombK_c3[-10,10]",
    "bkgCombK_c4[-10,10]",
    "EXPR::f_bkgCombA('({pdfL})*({pdfK})', {args})".format(
        pdfL="exp(-0.5*pow((CosThetaL-bkgCombL_c1)/bkgCombL_c2,2))+bkgCombL_c5*exp(-0.5*pow((CosThetaL-bkgCombL_c3)/bkgCombL_c4,2))",
        pdfK="1+bkgCombK_c1*CosThetaK+bkgCombK_c2*pow(CosThetaK,2)+bkgCombK_c3*pow(CosThetaK, 3)+bkgCombK_c4*pow(CosThetaK,4)",
        args="{CosThetaL, CosThetaK, bkgCombL_c1, bkgCombL_c2, bkgCombL_c3, bkgCombL_c4, bkgCombL_c5, bkgCombK_c1, bkgCombK_c2, bkgCombK_c3, bkgCombK_c4}")
]
f_analyticBkgCombA_format['abovePsi2sA'] = [
    "bkgCombL_c1[-3,3]",
    "bkgCombK_c1[-10,10]",
    "bkgCombK_c2[-10,10]",
    "bkgCombK_c3[-10,10]",
    "EXPR::f_bkgCombA('({pdfL})*({pdfK})', {args})".format(
        pdfL="1.+bkgCombL_c1*CosThetaL",
        pdfK="1.+bkgCombK_c1*CosThetaK+bkgCombK_c2*pow(CosThetaK,2)+bkgCombK_c3*pow(CosThetaK, 3)",
        args="{CosThetaL, CosThetaK, bkgCombL_c1, bkgCombK_c1, bkgCombK_c2, bkgCombK_c3}")
]
f_analyticBkgCombA_format['abovePsi2sB'] = [
    "bkgCombL_c1[-3,3]",
    "bkgCombK_c1[-10,10]",
    "bkgCombK_c2[-10,10]",
    "bkgCombK_c3[-10,10]",
    "EXPR::f_bkgCombA('({pdfL})*({pdfK})', {args})".format(
        pdfL="1.+bkgCombL_c1*CosThetaL",
        pdfK="1.+bkgCombK_c1*CosThetaK+bkgCombK_c2*pow(CosThetaK,2)+bkgCombK_c3*pow(CosThetaK, 3)",
        args="{CosThetaL, CosThetaK, bkgCombL_c1, bkgCombK_c1, bkgCombK_c2, bkgCombK_c3}")
]
f_analyticBkgCombA_format['summary'] = [
    "bkgCombL_c1[0.01,1]",
    "bkgCombL_c2[0.1,20]",
    "bkgCombL_c3[-1,1]",
    "bkgCombL_c4[0.05,1]",
    "bkgCombK_c1[-10,0]",
    "bkgCombK_c2[0,20]",
    "bkgCombK_c3[0,10]",
    "EXPR::f_bkgCombA('({pdfL})*({pdfK})',{args})".format(
        pdfL="1-pow(pow(CosThetaL,2)-bkgCombL_c1,2)+bkgCombL_c2*exp(-0.5*pow((CosThetaL-bkgCombL_c3)/bkgCombL_c4,2))",
        pdfK="exp(bkgCombK_c1*CosThetaK)+bkgCombK_c2*exp(bkgCombK_c3*CosThetaK)",
        args="{CosThetaL,CosThetaK,bkgCombL_c1,bkgCombL_c2,bkgCombL_c3,bkgCombL_c4,bkgCombK_c1,bkgCombK_c2,bkgCombK_c3}")
]
f_analyticBkgCombA_format['DEFAULT'] = f_analyticBkgCombA_format['summary']

setupBuildAnalyticBkgCombA = {
    'objName': "f_bkgCombA",
    'varNames': ["CosThetaK", "CosThetaL"],
    'factoryCmd': [
    ]
}

setupSmoothBkg={'factoryCmd': []}
SmoothBkgCmd={}
SmoothBkgCmd['DEFAULT']=[1.0, 1.0, 1.0, 1.0]
SmoothBkgCmd['belowJpsiC']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['belowJpsiA']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['belowJpsiB']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['betweenPeaks']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['abovePsi2sA']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['abovePsi2sB']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['summary']=[0.6, 0.6, 0.6, 0.6]
SmoothBkgCmd['summaryLowQ2']=[0.6, 0.6, 0.6, 0.6]
def buildSmoothBkgCombA(self, factoryCmd):
    """Build with RooWorkspace.factory. See also RooFactoryWSTool.factory"""
    wspace = self.getWspace()
    Cmd=factoryCmd
    f_bkgCombAAltA = wspace.pdf("f_bkgCombAAltA")
    if f_bkgCombAAltA == None:
        f_bkgCombAAltKUp = RooKeysPdf("f_bkgCombAAltKUp",
                                      "f_bkgCombAAltKUp",
                                      CosThetaK,
                                      self.process.sourcemanager.get('dataReader.USB'),
                                      RooKeysPdf.MirrorBoth, Cmd[0])
        f_bkgCombAAltKLo = RooKeysPdf("f_bkgCombAAltKLo",
                                      "f_bkgCombAAltKLo",
                                      CosThetaK,
                                      self.process.sourcemanager.get('dataReader.LSB'),
                                      RooKeysPdf.MirrorBoth, Cmd[1])
        f_bkgCombAAltLUp = RooKeysPdf("f_bkgCombAAltLUp",
                                      "f_bkgCombAAltLUp",
                                      CosThetaL,
                                      self.process.sourcemanager.get('dataReader.USB'),
                                      RooKeysPdf.MirrorBoth, Cmd[2])
        f_bkgCombAAltLLo = RooKeysPdf("f_bkgCombAAltLLo",
                                      "f_bkgCombAAltLLo",
                                      CosThetaL,
                                      self.process.sourcemanager.get('dataReader.LSB'),
                                      RooKeysPdf.MirrorBoth, Cmd[3])
        for f in f_bkgCombAAltKLo, f_bkgCombAAltKUp, f_bkgCombAAltLLo, f_bkgCombAAltLUp:
            getattr(wspace, 'import')(f)
        wspace.factory("PROD::f_bkgCombAAltAUp(f_bkgCombAAltKUp,f_bkgCombAAltLUp)")
        wspace.factory("PROD::f_bkgCombAAltALo(f_bkgCombAAltKLo,f_bkgCombAAltLLo)")
        wspace.factory("SUM::f_bkgCombAAltA(frac_bkgCombAAltA[0.5,0,1]*f_bkgCombAAltALo,f_bkgCombAAltAUp)")
        f_bkgCombAAltA = wspace.pdf("f_bkgCombAAltA")
        frac_bkgCombAAltA = wspace.var("frac_bkgCombAAltA")
        frac_bkgCombAAltA.setVal(self.process.sourcemanager.get('dataReader.LSB').sumEntries() / (self.process.sourcemanager.get('dataReader.LSB').sumEntries() + self.process.sourcemanager.get('dataReader.USB').sumEntries()))
        frac_bkgCombAAltA.setConstant(True)

    self.cfg['source']['frac_bkgCombAAltA'] = frac_bkgCombAAltA
    self.cfg['source']['f_bkgCombAAltA'] = f_bkgCombAAltA

def buildBkgComb(self):
    """Build with RooWorkspace.factory. See also RooFactoryWSTool.factory"""
    wspace = self.getWspace()

    variations = [("f_bkgComb", "f_bkgCombM", "f_bkgCombA"),
                  ("f_bkgCombAltA", "f_bkgCombM", "f_bkgCombAAltA"),
                  ("f_bkgCombAltM", "f_bkgCombMAltM", "f_bkgCombA")]
    for p, pM, pA in variations:
        f_bkgComb = wspace.pdf(p)
        if f_bkgComb == None:
            for k in [pM, pA]:
                locals()[k] = self.cfg['source'][k] if k in self.cfg['source'] else self.process.sourcemanager.get(k)
                if wspace.obj(k) == None:
                    getattr(wspace, 'import')(locals()[k])
            wspace.factory("PROD::{0}({1}, {2})".format(p, pM, pA))
            f_bkgComb = wspace.pdf(p)
        self.cfg['source'][p] = f_bkgComb

def buildFinal(self):
    """Combination of signal and background components."""
    wspace = self.getWspace()

    # Keep also mass spectrum only for prefit
    variations = [("f_final", "f_sig3D", "f_bkgComb"),
                  ("f_finalAltBkgCombA", "f_sig3D", "f_bkgCombAltA"),
                  ("f_finalAltBkgCombM", "f_sig3D", "f_bkgCombAltM"),
                  ("f_finalM", "f_sigM", "f_bkgCombM"),
                  ("f_finalMAltBkgCombM", "f_sigM", "f_bkgCombMAltM")]
    wspace.factory("nSig[10,1e-2,1e5]")
    wspace.factory("nBkgComb[100,1e-2,1e5]")
    for p, pSig, pBkg in variations:
        f_final = wspace.obj(p)
        if f_final == None:
            for k in [pSig, pBkg]:
                locals()[k] = self.cfg['source'][k] if k in self.cfg['source'] else self.process.sourcemanager.get(k)
                if wspace.obj(k) == None:
                    getattr(wspace, 'import')(locals()[k])
            wspace.factory("SUM::{0}(nSig*{1},nBkgComb*{2})".format(p, pSig, pBkg))
            f_final = wspace.obj(p)
        self.cfg['source'][p] = f_final

sharedWspaceTagString = "{binLabel}"
CFG_WspaceReader = copy(WspaceReader.templateConfig())
CFG_WspaceReader.update({
    'obj': OrderedDict([
    ])  # Empty by default loads all Functions and Pdfs
})
stdWspaceReader = WspaceReader(CFG_WspaceReader); stdWspaceReader.name="stdWspaceReader"
def customizeWspaceReader(self):
    self.cfg['fileName'] = "{0}/input/wspace_{1}.root".format(modulePath, q2bins[self.process.cfg['binKey']]['label'])
    self.cfg['wspaceTag'] = sharedWspaceTagString.format(binLabel=q2bins[self.process.cfg['binKey']]['label'])
stdWspaceReader.customize = types.MethodType(customizeWspaceReader, stdWspaceReader)

CFG_PDFBuilder = ObjProvider.templateConfig()
stdPDFBuilder = ObjProvider(copy(CFG_PDFBuilder)); stdPDFBuilder.name="stdPDFBuilder"
def customizePDFBuilder(self):
    print("""Customize pdf for q2 bins""")
    setupBuildAnalyticBkgCombA['factoryCmd'] = f_analyticBkgCombA_format.get(self.process.cfg['binKey'], f_analyticBkgCombA_format['DEFAULT'])
    setupBuildEffiSigA['factoryCmd'] = f_effiSigA_format.get(self.process.cfg['binKey'], f_effiSigA_format['DEFAULT'])
    for i in setupBuildEffiSigA['factoryCmd']:
        print("FactoryCMD: ", i)
    buildAnalyticBkgCombA = functools.partial(buildGenericObj, **setupBuildAnalyticBkgCombA)
    buildEffiSigA = functools.partial(buildGenericObj, **setupBuildEffiSigA)
    
    setupSmoothBkg['factoryCmd'] = SmoothBkgCmd.get(self.process.cfg['binKey'], SmoothBkgCmd['DEFAULT'])
    print setupSmoothBkg
    buildSmoothBkg = functools.partial(buildSmoothBkgCombA, **setupSmoothBkg)
    # Configure setup
    self.cfg.update({
        'wspaceTag': sharedWspaceTagString.format(binLabel=q2bins[self.process.cfg['binKey']]['label']),
        'obj': OrderedDict([
            ('effi_sigA', [buildEffiSigA]),
            ('f_sigA', [buildSigA]),
            ('f_sigM', [buildSigM]),
            ('f_sig3D', [buildSig]),  # Include f_sig2D
            ('f_bkgCombA', [buildAnalyticBkgCombA]),
            ('f_bkgCombAAltA', [buildSmoothBkg]),
            ('f_bkgCombM', [buildBkgCombM]),
            ('f_bkgCombMAltM', [buildBkgCombMAltM]),
            ('f_bkgComb', [buildBkgComb]),  # Include all variations
            ('f_final', [buildFinal]),  # Include all variations
        ])
    })
stdPDFBuilder.customize = types.MethodType(customizePDFBuilder, stdPDFBuilder)

if __name__ == '__main__':
    #  binKey = ['belowJpsiA', 'belowJpsiB', 'belowJpsiC', 'betweenPeaks', 'abovePsi2sA','abovePsi2sB', 'summary', 'summaryLowQ2']
    binKey = [sys.argv[1]]
    for b in binKey:
        p.cfg['binKey'] = b
        p.setSequence([dataCollection.dataReader, stdWspaceReader, stdPDFBuilder])
        p.beginSeq()
        p.runSeq()
        p.endSeq()

        #  p.reset()
        dataCollection.dataReader.reset()
        stdWspaceReader.reset()
        stdPDFBuilder.reset()
