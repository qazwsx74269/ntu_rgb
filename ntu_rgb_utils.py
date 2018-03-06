import sys
import pickle
import numpy as np
import scipy
from opengl_viewer.opengl_viewer import OpenGlViewer
from ntu_rgb import NTU


def record_multiple_voxel_flow():
    dataset = NTU()
    all_voxels = []
    for vid in range(int(sys.argv[1]) - 10, int(sys.argv[1])):
        all_voxels.append(dataset.get_voxel_flow(vid))
    voxel_flow = np.concatenate(all_voxels)
    print(voxel_flow.shape)
    viewer = OpenGlViewer(voxel_flow, record=True)
    viewer.view()


def view_one_voxel_flow():
    vox_flow = NTU().get_voxel_flow(57)

    ##### Rotate
    # vox_flow = scipy.ndimage.interpolation.rotate(vox_flow, 10, (2,4), reshape=False, order=0)

    OpenGlViewer(vox_flow).view()


if __name__ == '__main__':
    view_one_voxel_flow()
