import matplotlib
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mpl_toolkits.basemap
from mpl_toolkits.basemap import Basemap, maskoceans
import pygrib, os, sys
from netCDF4 import Dataset
from numpy import *
import numpy as np
from pylab import *
import time
from datetime import date, timedelta
from matplotlib import animation
import matplotlib.animation as animation
import types
import matplotlib.lines as mlines
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap
import nclcmaps
import pandas as pd
import xarray as xr
from scipy import interpolate
import operator
import multiprocessing


#Read in with xarray
ds = xr.open_dataset('/uufs/chpc.utah.edu/common/home/steenburgh-group7/tom/cm1/cm1r19B/run/cm1run_20ms_1500m_tug.nc')
#ds = xr.open_dataset('/uufs/chpc.utah.edu/common/home/steenburgh-group7/tom/cm1/output/netcdf_output/tug/cm1run_20ms_0000m_radiation_warmerlake.nc')



#xpos = np.load('xpos_traj_500m.npy')
#ypos = np.load('ypos_traj_500m.npy')
#zpos_terrain = np.load('zpos_traj_500m.npy')
#color = np.load('color_traj_500m.npy')


###############################################################################
###############################################################################   
##########################   Set up Trajectories ##############################
###############################################################################
###############################################################################


#Dimension size variables
num_x = ds.uinterp[0,0,0,:].size
num_y = ds.uinterp[0,0,:,0].size
num_z = ds.uinterp[0,:,0,0].size

x = np.arange(0,num_x,1)
y = np.arange(0,num_y,1)
z = np.arange(0,num_z,1)



###############################################################################
##################### INFO TO CALCULATE SEEDS #################################
#############  These are variables the user changes  ##########################
###############################################################################
#Backward trajectories
num_seeds_z = 151 #Up to 5000m (3 seeds every vertical grid point)
num_seeds_x = ds.nx #One for each x gridpoint
time_steps = 60 #Number of time steps to run trajectories back
start_time_step = 260 #Starting time step
hor_resolution = 200 #[meters]
time_step_length = 120.0 #[seconds]
###############################################################################
###############################################################################


#Create arrays for location and variable color of parcels
xpos = np.zeros((time_steps, num_seeds_z, num_seeds_x))
ypos = np.zeros((time_steps, num_seeds_z, num_seeds_x))
zpos = np.zeros((time_steps, num_seeds_z, num_seeds_x))
zpos_grid = np.zeros((time_steps, num_seeds_z, num_seeds_x))
  

###############################################################################
##################### INITIAL LOCATION OF SEEDS ###############################
#########  (These may also be important to the user)  #########################
###############################################################################
#Choose starting point 
#xpos
for i in range(0, num_seeds_x, 1):
    xpos[0,:,i] = i#Seeds at every x-gridpoint

#ypos   
ymid = np.int(ds.ny/2)
ypos[0,:,:] = ymid #Seeds all at middle y-gridpoint



##############################   zpos    ######################################
for i in range(num_seeds_z):
    zpos[0,i,:] = i/3.0 #Surface to top of desired regions (3 per z-gridpoint)



#####  Use model terrain to correct errors from computing trajectories with
#####  with terrain following coordinates
    
#check if run has terrain (if not, zs is zero and zpos should not be affected)
try:
    zh = np.array(ds.zh[0,:,:,:])
except:
    zh = np.zeros((ds.nz,ds.ny, ds.nx))
    
#Add terrain height
#Create list of current coordinates for terrain addition

xloc = np.array(xpos[0,:,:]).flatten()
yloc = np.array(ypos[0,:,:]).flatten()
zloc = np.array(zpos[0,:,:]).flatten()
coor_terrain = []
for i in range(len(xloc)):
    coor_terrain.append((zloc[i], yloc[i], xloc[i]))

zpos_terrain = np.array(zpos)
zpos_terrain[0,:,:] = np.reshape(interpolate.interpn((z,y,x), zh, coor_terrain, method='linear', bounds_error=False, fill_value= 0), (num_seeds_z, num_seeds_x))

#This gets us the grid spacing for the vertical grid
z_grid = zh[1:,:,:]-zh[:-1,:,:]

###############################################################################
###############################################################################
#%%
       
###############################################################################
###############################################################################   
##########################  Calculate Trajectories ############################
###############################################################################
###############################################################################

#Loop over all time spteps and compute trajectory
for t in range(time_steps-1):
    
    print t
    start = time.time() #Timer
    

    #Create list of current coordinates
    xloc = np.array(xpos[t,:,:]).flatten()
    yloc = np.array(ypos[t,:,:]).flatten()
    zloc = np.array(zpos[t,:,:]).flatten()
    
    coor = []
    for i in range(len(xloc)):
        coor.append((zloc[i], yloc[i], xloc[i]))
    coor_array = np.array(coor)
    

    ###########  Interpolation function only accepts arrays with all values ########
    # All code code in this chuck was developed to speed up placing the 
    # huge data arrays into numpy arrays. The main idea is to extract 
    # the chunkc of data that is necessary to interpolate at all points
    # along the trajectory

    #Create arrays of zeros to place data chunks in to maintain locations
    u = np.zeros((ds.uinterp[0,:,0,0].size, ds.uinterp[0,0,:,0].size, ds.uinterp[0,0,0,:].size))
    v = np.zeros((ds.uinterp[0,:,0,0].size, ds.uinterp[0,0,:,0].size, ds.uinterp[0,0,0,:].size))
    w = np.zeros((ds.uinterp[0,:,0,0].size, ds.uinterp[0,0,:,0].size, ds.uinterp[0,0,0,:].size))

    #Number of surrounding points to use.  2 is min necessary for linear interp
    size = 2
    
    #Check if they've all left the domain
    if np.all(np.isnan(coor_array)):
        xmin, xmax, ymin, ymax = (0,0,0,0)
    else:
        #Find max and min in each direction for entire set of coordinates
        xmin = np.int(np.nanmin(coor_array[:,2]))-size
        xmax = np.int(np.nanmax(coor_array[:,2]))+size
        ymin = np.int(np.nanmin(coor_array[:,1]))-size
        ymax = np.int(np.nanmax(coor_array[:,1]))+size
        zmin = np.int(np.nanmin(coor_array[:,0]))-size
        zmax = np.int(np.nanmax(coor_array[:,0]))+size

    #Make sure points don't leave domain
    if xmin < 0:
        xmin = 0
    if ymin < 0:
        ymin = 0
    if zmin < 0:
        zmin = 0

    if xmax > ds.uinterp[0,0,0,:].size:
        xmax = ds.uinterp[0,0,0,:].size
    if ymax > ds.uinterp[0,0,:,0].size:
        ymax = ds.uinterp[0,0,:,0].size
    if zmax > ds.uinterp[0,:,0,0].size:
        zmax = ds.uinterp[0,:,0,0].size

    #Specify and add necessary chunk of data to arrays with zeros
    u[zmin:zmax,ymin:ymax,xmin:xmax] = ds.uinterp[start_time_step-t,zmin:zmax,ymin:ymax,xmin:xmax].values
    v[zmin:zmax,ymin:ymax,xmin:xmax] = ds.vinterp[start_time_step-t,zmin:zmax,ymin:ymax,xmin:xmax].values
    w[zmin:zmax,ymin:ymax,xmin:xmax] = ds.winterp[start_time_step-t,zmin:zmax,ymin:ymax,xmin:xmax].values
    

    #Timer
    stop = time.time()
    print(stop-start)


            
    #####################   Calc new xpos #####################################
    xpos[t+1,:,:] = xpos[t,:,:] - np.reshape(interpolate.interpn((z,y,x), u, coor, method='linear', bounds_error=False, fill_value=np.nan)*time_step_length/hor_resolution, (num_seeds_z, num_seeds_x))

    #####################   Calc new ypos #####################################
    ypos[t+1,:,:]  = ypos[t,:,:] - np.reshape(interpolate.interpn((z,y,x), v, coor, method='linear', bounds_error=False, fill_value=np.nan)*time_step_length/hor_resolution, (num_seeds_z, num_seeds_x))

    #####################   Calc new zpos #####################################
    #zpos grid spacing
    zpos_grid[t,:,:] = np.reshape(interpolate.interpn((z[:-1],y,x), z_grid, coor, method='linear', bounds_error=False, fill_value= 0), (num_seeds_z, num_seeds_x))
    #terrain-following
    zpos[t+1,:,:]  = zpos[t,:,:] - np.reshape(interpolate.interpn((z,y,x), w, coor, method='linear', bounds_error=False, fill_value= 0), (num_seeds_z, num_seeds_x))*time_step_length/zpos_grid[t,:,:]
    #terrain-height coordinates
    zpos_terrain[t+1,:,:]  = zpos_terrain[t,:,:] - np.reshape(interpolate.interpn((z,y,x), w, coor, method='linear', bounds_error=False, fill_value= 0)*time_step_length, (num_seeds_z, num_seeds_x))

    
    zpos = zpos.clip(min=0) #Prevents z from being negative



   
    
#Save arrays
np.save('xpos_traj_disp', xpos)
np.save('ypos_traj_disp', ypos)
np.save('zpos_traj_disp', zpos_terrain)
np.save('zpos_grid_traj_disp', zpos_grid)

#%%
#xpos = np.load('xpos_traj_disp.npy')
#ypos = np.load('ypos_traj_disp.npy')
#zpos_terrain = np.load('zpos_traj_disp.npy')
#zpos_grid = np.load('zpos_grid_traj_disp.npy')

###############################################################################
######################  Calculate displacement  ###############################
###############################################################################


##### ENTER VALUE FOR NUMBER OF TIME STEPS BACK TO CALCULATE TIME-MEAN AND PLOT
ts_plot = 60

z_disp = np.zeros((time_steps-2, num_seeds_z, num_seeds_x))
x_disp = np.zeros((time_steps-2, num_seeds_z, num_seeds_x))
y_disp = np.zeros((time_steps-2, num_seeds_z, num_seeds_x))

for t in range(time_steps-2):
    z_disp[t,:,:] = zpos_terrain[0,:,:] - zpos_terrain[t+1,:,:]
    #z_disp[t,:,:] = zpos[0,:,:] - zpos[t+1,:,:]
    x_disp[t,:,:] = xpos[0,:,:] - xpos[t+1,:,:]
    y_disp[t,:,:] = ypos[0,:,:] - ypos[t+1,:,:]

mean_z_disp = np.zeros((num_seeds_z, num_seeds_x))
mean_z_disp = np.mean(z_disp[:ts_plot,:,:], axis = 0)

mean_x_disp = np.zeros((num_seeds_z, num_seeds_x))
mean_x_disp = np.mean(x_disp[:ts_plot,:,:], axis = 0)

mean_y_disp = np.zeros((num_seeds_z, num_seeds_x))
mean_y_disp = np.mean(y_disp[:ts_plot,:,:], axis = 0)










#%%

###############################################################################
#############################   PLOTS   #######################################
###############################################################################



############## Set ncl_cmap as the colormap you want ##########################

### 1) In order for this to work the files "nclcmaps.py" and "__init__.py"
### must be present in the dirctory.
### 2) You must "import nclcmaps"
### 3) The path to nclcmaps.py must be added to tools -> PYTHONPATH manager in SPyder
### 4) Then click "Update module names list" in tolls in Spyder and restart Spyder
                
## The steps above describe the general steps for adding "non-built in" modules to Spyder

###############################################################################
###############################################################################


#Read in colormap and put in proper format
colors1 = np.array(nclcmaps.colors['amwg256'])#perc2_9lev'])
colors_int = colors1.astype(int)
colors = list(colors_int)
cmap_dth = nclcmaps.make_cmap(colors, bit=True)


#Read in colormap and put in proper format
colors1 = np.array(nclcmaps.colors['WhiteBlueGreenYellowRed'])#perc2_9lev'])
colors_int = colors1.astype(int)
colors = list(colors_int)
cmap_th = nclcmaps.make_cmap(colors, bit=True)



##########  Create Grid ########
### The code below makes the data terrain following 
x1d = np.arange(0,num_seeds_x,1)
y1d = np.arange(0,num_seeds_z,1)
z = np.array(ds.zs[0,ymid,:num_seeds_x])/1000*30 #Div by 1000 to go to m and mult by 30 to match y dim

#Create 2D arrays for plotting data
x2d = np.zeros((num_seeds_z, num_seeds_x))
y2d = np.zeros((num_seeds_z, num_seeds_x))

for i in range(num_seeds_z):
    x2d[i,:] = x1d
for j in range(num_seeds_x):
    y2d[:,j] = y1d+z[j]
        
#Variables for plotting
xmin = 0
xmax = num_seeds_x
xlen = xmax-xmin

zmin = 0
zmax = num_seeds_z



###############################################################################
############ FILL OUT TO CHOOSE WHICH AREA OF GRID TO PLOT   ##################
###############################################################################

xleft = 800
xright = 1650

###############################################################################


##############################   Plot ########################################

    
fig = plt.figure(num=None, figsize=(18,9),  facecolor='w', edgecolor='k')
for j in range(1,3):
    subplot = 210 + j
    ax = plt.subplot(subplot,aspect = 'equal')
    plt.subplots_adjust(left=0.04, bottom=0.1, right=0.9, top=0.95, wspace=0, hspace=0)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.yaxis.set_ticks_position('left')
    ax.xaxis.set_ticks_position('bottom')
    

    
    ##Levels variable 1
    zlmin = -1000
    zlmax = 2000.01
    zlevels = np.arange(zlmin,zlmax, 50)
    zlevels_ticks = np.arange(zlmin,zlmax,500)
    zlevels_ticks_labels = np.arange(zlmin,zlmax, 500).astype(int)
    
    #Levels variable 2
    xlmin = -20
    xlmax = 80.01
    xlevels = np.arange(xlmin,xlmax, 1)
    xlevels_ticks = np.arange(xlmin,xlmax,10)
    xlevels_ticks_labels = np.arange(xlmin,xlmax, 10).astype(int)
    
    
###############################################################################
###############################################################################

    
    def shiftedColorMap(cmap, start=0, midpoint=0.5, stop=1.0, name='shiftedcmap'):
        '''
        Function to offset the "center" of a colormap. Useful for
        data with a negative min and positive max and you want the
        middle of the colormap's dynamic range to be at zero
    
        Input
        -----
          cmap : The matplotlib colormap to be altered
          start : Offset from lowest point in the colormap's range.
              Defaults to 0.0 (no lower ofset). Should be between
              0.0 and `midpoint`.
          midpoint : The new center of the colormap. Defaults to 
              0.5 (no shift). Should be between 0.0 and 1.0. In
              general, this should be  1 - vmax/(vmax + abs(vmin))
              For example if your data range from -15.0 to +5.0 and
              you want the center of the colormap at 0.0, `midpoint`
              should be set to  1 - 5/(5 + 15)) or 0.75
          stop : Offset from highets point in the colormap's range.
              Defaults to 1.0 (no upper ofset). Should be between
              `midpoint` and 1.0.
        '''
        cdict = {
            'red': [],
            'green': [],
            'blue': [],
            'alpha': []
        }

        # regular index to compute the colors
        reg_index = np.linspace(start, stop, 257)
    
        # shifted index to match the data
        shift_index = np.hstack([
            np.linspace(0.0, midpoint, 128, endpoint=False), 
            np.linspace(midpoint, 1.0, 129, endpoint=True)
        ])
    
        for ri, si in zip(reg_index, shift_index):
            r, g, b, a = cmap(ri)
    
            cdict['red'].append((si, r, r))
            cdict['green'].append((si, g, g))
            cdict['blue'].append((si, b, b))
            cdict['alpha'].append((si, a, a))
    
        newcmap = matplotlib.colors.LinearSegmentedColormap(name, cdict)
        plt.register_cmap(cmap=newcmap)

        return newcmap
###############################################################################
###############################################################################


    shifted_cmapz = shiftedColorMap(cmap_dth, midpoint=1 - zlmax/(zlmax + abs(zlmin)), name='shifted')
    shifted_cmapx = shiftedColorMap(cmap_dth, midpoint=1 - xlmax/(xlmax + abs(xlmin)), name='shifted')
    
    #Plot variables
    z = zpos_terrain[0,:,xleft:xright]/100*3
    if j == 1:
        z_disp_plot = plt.contourf(xpos[0,:,xleft:xright], z, mean_z_disp[:,xleft:xright], zlevels, cmap = shifted_cmapz, alpha = 1, zorder = 3, extend = 'both')
        #z_disp_plot = plt.contourf(x1d, y1d, mean_var1_disp, zlevels,  cmap = cmap_dth, vmin = -zlmax, alpha = 1, zorder = 3)

    if j == 2:
        #x_disp_plot = plt.contourf(x2d, y2d, mean_var2_disp, xlevels,  cmap = cmap_var,vmin = -xlmax, alpha = 1, zorder = 3)
        x_disp_plot = plt.contourf(xpos[0,:,xleft:xright], z, mean_x_disp[:,xleft:xright]*hor_resolution/1000, xlevels,  cmap = shifted_cmapx, alpha = 1, zorder = 3, extend = 'both') #Percentage
        #x_disp_plot = plt.contourf(x1d, y1d, variable1[0,:,:], zlevels,  cmap = cmap_dth, alpha = 0.5, zorder = 4) #Percentage
    
    #Plot Terrain
    z_terrain  = zpos_terrain[0,0,xleft:xright]/100*3-2
    terrain = plt.plot(x1d[xleft:xright], z_terrain, c = 'slategrey', linewidth = 5)
    
    #Plot Lake
    lake = ds.xland[0,ymid,:].values
    lake[lake == 1] = np.nan
    lake_plt = plt.plot(x1d[xleft:xright], lake[xleft:xright]-2, c = 'blue', linewidth = 4, zorder = 6)
    
    
    #Title
    if j == 2:
        sub_title = '[Run: 20 $\mathregular{ms^{-1}}$ and 1500m]'
        ax.text(1430, -50, sub_title, fontsize = 20)
    
    
    ### Label and define grid area
    #y-axis
    plt.ylim([-3,np.max(y2d[:,0])+1])
    plt.yticks(np.arange(0, np.max(y2d[:,0]+1),30))
    ax.set_yticklabels(np.arange(0,np.max(y2d[:,0]+1),1).astype(int), fontsize = 15, zorder = 6)
    #x-axis
    plt.xticks(np.arange(0,ds.nx, 100))
    ax.set_xticklabels(np.arange(0, ds.nx*hor_resolution/1000, 100*hor_resolution/1000).astype(int), fontsize = 15)
    plt.xlim([xleft,xright])
    #axis labels
    plt.ylabel('Height (km)', fontsize = 20, labelpad = 8)
    if j == 2:
        plt.xlabel('Distance within Domain (km)', fontsize = 20, labelpad = 9)
                
    #Colorbar
    if j == 1:
        zcbaxes = fig.add_axes([0.92, 0.59, 0.03, 0.3])             
        zcbar = plt.colorbar(z_disp_plot, cax = zcbaxes, ticks = zlevels_ticks)
        zcbar.ax.set_yticklabels(zlevels_ticks_labels)
        zcbar.ax.tick_params(labelsize=15)
        plt.text(0.25, -0.17, 'm', fontsize = 21)
        
    if j == 2:
        xcbaxes = fig.add_axes([0.92, 0.16, 0.03, 0.3])             
        xcbar = plt.colorbar(x_disp_plot, cax = xcbaxes, ticks = xlevels_ticks)
        xcbar.ax.set_yticklabels(xlevels_ticks_labels)
        xcbar.ax.tick_params(labelsize=15)
        plt.text(0.1, -0.17, 'km', fontsize = 21)
    
    #Labels
    if j == 1:
        sub_title = "Time-mean Vertical Displacement"
    if j == 2:
        sub_title = 'Time-mean Streamwise Displacement'
    props = dict(boxstyle='square', facecolor='white', alpha=1)
    ax.text(815, 125, sub_title, fontsize = 20, bbox = props, zorder = 5)


plt.savefig("/uufs/chpc.utah.edu/common/home/u1013082/public_html/phd_plots/cm1/plots/time_mean_dsp_1500m_20ms_corrected_z.png", dpi=350)
plt.close(fig)



