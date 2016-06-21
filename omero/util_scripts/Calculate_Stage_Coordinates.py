#!/usr/bin/env python

import omero
from omero.gateway import BlitzGateway
import omero.scripts as scripts
from omero.rtypes import rlong, rstring, robject
import omero.util.script_utils as script_utils
from omero.sys import ParametersI


def processImages(client, conn, scriptParams):
    """
    Process the script params to make a list of channel_offsets, then iterate
    through the images creating a new image from each with the specified
    channel offsets
    """

    message = ""

    # Get the images
    objects, logMessage = script_utils.getObjects(conn, scriptParams)
    message += logMessage
    if not objects:
        return None, None, message

    # Concatenate images from datasets
    if scriptParams["Data_Type"] == "Image":
        images = objects
    else:
        images = []
        for ds in objects:
            images += ds.listChildren()

    queryService = conn.getQueryService()
    roiService = conn.getRoiService()

    print "Showing X ; Y coordinates in micrometer"

    for image in images:

         print "---------- {0} ---------- ".format(image.getName())

         metadata = dict(image.loadOriginalMetadata()[1])
         
         params = ParametersI()
         params.addId(image.getId())
         
         roiResult = roiService.findByImage(image.getId(), None)

         for roi in roiResult.rois:
              for shape in roi.copyShapes():
                   if type(shape) != omero.model.PointI:
                        continue
                   
                   # From tem-hole-finder:XYpic2XYstage.m
                   # RotM=1e-9*[tt(1),tt(2);tt(3),tt(4)];
                   # Offset=1e-6*[tt(5),tt(6)];
                   # XYstageHoles=RotM*XYpixHolesOverview'+repmat(Offset',[1,l1]);

                   # TODO: Eval is of course not really safe...
                   tt = eval(metadata['Conversion matrix'])
                   
                   RotM = [x * 1e-9 for x in [tt[0], tt[1], tt[2], tt[3]]]
                   Offset = [x * 1e-6 for x in [tt[4], tt[5]]]

                   xRoi = int(shape.getCx().getValue())
                   yRoi = int(shape.getCy().getValue())

                   stageX = RotM[0] * xRoi + RotM[1] * yRoi + Offset[0]
                   stageY = RotM[2] * xRoi + RotM[3] * yRoi + Offset[1]
                   name = roi.getName().getValue() if roi.getName() is not None else "Unnamed"

                   print "{0} [ {1} ; {2} ] ".format(name, stageX * 1e6, stageY * 1e6)

         print "--------------------------------------"

    return "Finished calculating"


def runAsScript():

    dataTypes = [rstring('Image'), rstring('Dataset')]

    client = scripts.client(
        'Calculate_Stage_Coordinates.py',
        """Calculate Stage Coordinates from point ROIs in micrometer""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Pick Images by 'Image' ID or by the ID of their "
            "Dataset'", values=dataTypes, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs to "
            "process.").ofType(rlong(0)),

        version="1.0.0",
        authors=["Paul van Schayck"],
        institutions=["Maastricht University"],
        contact="p.vanschayck@maastrichtuniversity.nl",
    )

    try:
        scriptParams = client.getInputs(unwrap=True)
        print scriptParams

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        message = processImages(client, conn, scriptParams)

        # Return message, new image and new dataset (if applicable) to the
        # client
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()

if __name__ == "__main__":
    runAsScript()
