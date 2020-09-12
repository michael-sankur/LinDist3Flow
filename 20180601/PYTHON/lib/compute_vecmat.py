import numpy as np
import opendssdirect as dss
import re
def compute_vecmat(XNR, fn, Vslack):

    dss.run_command('Redirect ' + fn)
    nline = len(dss.Lines.AllNames())
    nnode = len(dss.Circuit.AllBusNames())
    dss.Circuit.SetActiveBus(dss.Circuit.AllBusNames()[0])
    Vbase = dss.Bus.kVBase() * 1000
    Sbase = 1000000.0

    Ibase = Sbase/Vbase
    Zbase = Vbase/Ibase

    ## {bus : [1 x 3 phase existence]}
    def bus_phases():
        dictionary = {}
        for k2 in range(len(dss.Circuit.AllNodeNames())):
            a, b = dss.Circuit.AllNodeNames()[k2].split('.')
            if a in dictionary:
                temp = dictionary[a]
                temp[int(b) - 1] = 1
                dictionary[a] = temp
            elif a not in dictionary:
                dictionary[a] = [0, 0, 0]
                temp = dictionary[a]
                temp[int(b) - 1] = 1
                dictionary[a] = temp
        return dictionary

    #bus phases
    def identify_bus_phases(bus):
        k = np.zeros(3)
        for i in range(1, 4):
            pattern = r"\.%s" % (str(i))
            m = re.findall(pattern, bus)
            if m:
                k[i - 1] = 1
        return k

    #line phases
    def identify_line_phases(line):
        k = np.zeros(3)
        dss.Lines.Name(line)
        bus = dss.Lines.Bus1()
        for i in range(1, 4):
            pattern = r"\.%s" % (str(i))
            m = re.findall(pattern, bus)
            if m:
                k[i - 1] = 1
        return k

    # Residuals for slack node voltage
    # Generate resistance and reactance matrices
    R_matrix = np.zeros((nline,9))
    X_matrix = np.zeros((nline,9))

    dss.Circuit.SetActiveBus(dss.Circuit.AllBusNames()[0])
    bus_phase_dict = bus_phases()

    for k2 in range(len(dss.Lines.AllNames())):
        dss.Lines.Name(dss.Lines.AllNames()[k2]) #set the line
        linecode = dss.Lines.LineCode() #get the linecode
        dss.LineCodes.Name(linecode) #set the linecode
        xmat = dss.LineCodes.Xmatrix() #get the xmat
        rmat = dss.LineCodes.Rmatrix() #get the rmat

        line_phases = identify_line_phases(dss.Lines.AllNames()[k2])
        if len(xmat) == 9:
            for i in range(len(xmat)):
                X_matrix[k2][i] = xmat[i] #fill x/r where they are shaped like nline x 9 (for 9 components)
                R_matrix[k2][i] = rmat[i]
        elif len(xmat) == 1:
            X_matrix[k2][0] = xmat[0]
            X_matrix[k2][4] = xmat[0] #set the diagonals to the value
            X_matrix[k2][8] = xmat[0]
            R_matrix[k2][0] = rmat[0]
            R_matrix[k2][4] = rmat[0]
            R_matrix[k2][8] = rmat[0]
        elif len(xmat) == 4:
            xmat = np.reshape(xmat, (2,2))
            rmat = np.reshape(rmat, (2,2))
            if line_phases[0] == 0: #becomes [0, 0, 0; 0, b, c; 0, d, e]
                xmatt = np.vstack([np.zeros((1,2)),xmat[:,:]])
                xmatt2 = np.hstack((np.zeros((3,1)), xmatt[:, :]))
                X_matrix[k2, :] = xmatt2.flatten()
                r_temp = np.vstack([np.zeros((1,2)),rmat[:,:]])
                r_temp2 = np.hstack((np.zeros((3,1)), r_temp[:, :]))
                R_matrix[k2, :] = r_temp2.flatten()
            elif line_phases[1] == 0: #becomes [a, 0, c; 0, 0, 0; a, 0, c]
                xmatt = np.vstack((np.vstack((xmat[0,:], np.zeros((1,2)))), xmat[len(xmat)-1,:]))
                xmatt2 = np.hstack((np.hstack((np.reshape(xmatt[:, 0], (3, 1)), np.zeros((3,1)))), np.reshape(xmatt[:, len(xmatt[0])-1], (3,1))))
                X_matrix[k2, :] = xmatt2.flatten()
                r_temp = np.vstack([np.vstack([rmat[0,:], np.zeros((1,2))]), rmat[len(xmat)-1,:]])
                r_temp2 = np.hstack((np.hstack((np.reshape(r_temp[:, 0], (3, 1)), np.zeros((3,1)))), np.reshape(r_temp[:, len(r_temp[0])-1], (3,1))))
                R_matrix[k2, :] = r_temp2.flatten()
            else:
                xmatt = np.vstack([xmat[:,:],np.zeros((1,2))])
                xmatt2 = np.hstack((xmatt[:, :], np.zeros((3,1))))
                X_matrix[k2, :] = xmatt2.flatten()
                r_temp = np.vstack([rmat[:,:],np.zeros((1,2))])
                r_temp2 = np.hstack((r_temp[:, :], np.zeros((3,1))))
                R_matrix[k2, :] = r_temp2.flatten()

        X_matrix[k2, :] = X_matrix[k2, :] * dss.Lines.Length() * 0.3048 #in feet for IEEE13
        R_matrix[k2, :] = R_matrix[k2, :] * dss.Lines.Length() * 0.3048

    X = np.reshape(XNR, (2*3*(nnode+nline), 1 ))

    R_matrix = R_matrix/Zbase/1609.34 #in miles for IEEE 13
    X_matrix = X_matrix/Zbase/1609.34 #

    #------------ slack bus ------------------


    #g_SB = np.array([]) #assumes slack bus is at index 0
    g_SB = np.zeros((6, 2*3*(nnode+nline)))
    sb_idx = [0, 1, 2*nnode, (2*nnode)+1, 4*nnode, (4*nnode)+1]
    for i in range(len(sb_idx)):
        g_SB[i, sb_idx[i]] = 1

    b_SB = np.zeros((6,1))
    for i in range(3):
        b_SB[2*i, 0] = Vslack[i].real
        b_SB[(2*i) + 1] = Vslack[i].imag


    #--------Residuals for KVL across line (m,n)-----------

    #G_KVL = np.array([])
    G_KVL = np.zeros((2*3*nline, 2*3*(nnode+nline)))

    for ph in range(0, 3):
        for line in range(len(dss.Lines.AllNames())):
            dss.Lines.Name(dss.Lines.AllNames()[line]) #set the line
            bus1 = dss.Lines.Bus1()
            bus2 = dss.Lines.Bus2()
            pattern =  r"(\w+)\."

            bus1_idx = dss.Circuit.AllBusNames().index(re.findall(pattern, bus1)[0]) #get the buses of the line
            bus2_idx = dss.Circuit.AllBusNames().index(re.findall(pattern, bus2)[0])

            b1, b2 = dss.CktElement.BusNames() #the buses on a line should have the same phase
            bus1_phases = identify_bus_phases(b1) #identifies which phase is associated with the bus (which is the same as the line)

            #real part of KVL residual
            #assigning the re voltage coefficients

            if bus1_phases[ph] == 1:
                G_KVL[2*ph*nline + 2*line][2*(nnode)*ph + 2*(bus1_idx)] = 1 #A_m
                G_KVL[2*ph*nline + 2*line][2*(nnode)*ph + 2*(bus2_idx)] = -1 #A_n
                G_KVL[2*ph*nline + 2*line][2*3*(nnode) + 2*line] = -R_matrix[line][ph*3] * bus1_phases[0] #C_mn for a
                G_KVL[2*ph*nline + 2*line][2*3*(nnode) + 2*line + 1] = X_matrix[line][ph*3] * bus1_phases[0] #D_mn for a
                G_KVL[2*ph*nline + 2*line][2*3*(nnode) + 2*nline + 2*line] = -R_matrix[line][ph*3 + 1] * bus1_phases[1] #C_mn for b
                G_KVL[2*ph*nline + 2*line][2*3*(nnode) + 2*nline + 2*line + 1] = X_matrix[line][ph*3 + 1] * bus1_phases[1] #D_mn for b
                G_KVL[2*ph*nline + 2*line][2*3*(nnode) + 4*nline + 2*line] = -R_matrix[line][ph*3 + 2] * bus1_phases[2] #C_mn for c
                G_KVL[2*ph*nline + 2*line][2*3*(nnode) + 4*nline + 2*line + 1] = X_matrix[line][ph*3 + 2] * bus1_phases[2] #D_mn for c

                G_KVL[2*ph*nline + 2*line+1][2*(nnode)*ph + 2*(bus1_idx) + 1] = 1 #B_m
                G_KVL[2*ph*nline + 2*line+1][2*(nnode)*ph + 2*(bus2_idx) + 1] = -1 #B_n
                G_KVL[2*ph*nline + 2*line+1][2*3*(nnode) + 2*line] = -X_matrix[line][ph*3] * bus1_phases[0] #C_mn for a
                G_KVL[2*ph*nline + 2*line+1][2*3*(nnode) + 2*line + 1] = -R_matrix[line][ph*3] * bus1_phases[0] #D_mn for a
                G_KVL[2*ph*nline + 2*line+1][2*3*(nnode) + 2*nline + 2*line] = -X_matrix[line][ph*3 + 1] * bus1_phases[1] #C_mn for b
                G_KVL[2*ph*nline + 2*line+1][2*3*(nnode) + 2*nline + 2*line + 1] = -R_matrix[line][ph*3 + 1] * bus1_phases[1] #D_mn for b
                G_KVL[2*ph*nline + 2*line+1][2*3*(nnode) + 4*nline + 2*line] = -X_matrix[line][ph*3 + 2] * bus1_phases[2] #C_mn for c
                G_KVL[2*ph*nline + 2*line+1][2*3*(nnode) + 4*nline + 2*line + 1] = -R_matrix[line][ph*3 + 2] * bus1_phases[2] #D_mn for c
            #same as above for imaginary part of KVL residual
            else:
                G_KVL[2*ph*nline + 2*line][2*(nnode)*3 + 2*ph*nline + 2*line] = 1 #C_mn
                G_KVL[2*ph*nline + 2*line+1][2*(nnode)*3 + 2*ph*nline + 2*line+1] = 1 #D_mn


    b_kvl = np.zeros((2*3*nline, 1))

    return X, g_SB, b_SB, G_KVL, b_kvl