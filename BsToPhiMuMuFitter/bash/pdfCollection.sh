#!/bin/bash

for arg in 'belowJpsiA' 'belowJpsiB' 'belowJpsiC' 'betweenPeaks' 'abovePsi2sA' 'abovePsi2sB' 
do
    echo -e "\n>>>>>>> File: pdfCollection.py, Where?: Entering Bin $arg <<<<<<<\n"
    python pdfCollection.py $arg
done
