
Urbafoam
========
A tool for generating and post processing OpenFOAM cases for urban wind analysis. It had been tested
on Ubunutu 20.04 and OpenFOAM v8 from https://openfoam.org/. You must have OpenFOAM installed and
working to use this. Urbafoam is primarily designed for doing quick indicative studies of urban wind comfort
and will make certain assumptions and take certain shortcuts to speed up the simulation, and while these should
work in the general case they might not always be correct in your case. If you're going to be using the results for something important you should get someone that knows CFD to look it over


Quick start

    urbafoam setup --quality (quick|normal) --model /path/to/buildings.stl outdir

where `buildings.stl` is a 3d model of the buildings you want to run your wind simulation on.
Currently only stl format is accepted.
Urbafoam assumes that the ground is a plane at height 0 and all buildings are resting on that plane.
The buildings models must be watertight and error free for the best results. Any problems with the
meshes can lead to crashes or bad simulation results

This will generate set of files and folders in `outdir` with default settings.

The file `urbafoam.toml` contains the settings for the simulations.
To change any of the defaults you can edit this file and rerun

    urbafoam setup outdir

and it will regenerate the case base on the changes you've made.
Your out directory will also contain a directory for each wind direction and a script RunAllCases
runs the simulation for all the wind directions.

Before running RunAllCases it's a good idea to cd into one of the wind directions and run the RunMesh script, which
loads and meshes the .stl file.
If this runs without error you can use `paraview` to view the resulting mesh.  If it looks good you can run RunAllCases
to run the whole simulation

Once all the cases have run successfully you can run

    urbafoam postprocess outdir

to postprocess the cases and get the wind speedup results as either cvs,shp or geojson





