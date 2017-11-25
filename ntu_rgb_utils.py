from OpenGL.GLUT import *
from OpenGL.GLU import *
from OpenGL.GL import *
import sys
import datetime as dt
import time
import numpy as np
import pickle
import line_profiler
from tqdm import tqdm
from scipy.ndimage.filters import gaussian_filter
from opengl_viewer.camera import Camera


width, height = 1000, 800
step_size0 = 0.05
rotation_angle0 = 2 * np.pi/180




# Arrow shape
s = 0.001
arrow_idxs = np.array([
    0, 1, 2, 2, 3, 0,   0, 4, 5, 5, 1, 0,   1, 5, 6, 6, 2, 1,
    2, 6, 7, 7, 3, 2,   3, 7, 4, 4, 0, 3,   4, 7, 6, 6, 5, 4,
    3, 2, 8,   2, 6, 8,   6, 7, 8,   7, 3, 8,
])
arrow_verts = np.array([
    [-s, -s, -s], [ s, -s, -s], [ s,  s, -s], [-s,  s, -s],
    [-s, -s,  s], [ s, -s,  s], [ s,  s,  s], [-s,  s,  s], [ 0,  s,  0],
])


# Pyramid shape
s = 0.0025
pyramid_idxs = np.array([0, 1, 2, 0, 1, 3, 1, 2, 3, 2, 0, 3,])
pyramid_verts = np.array([[0, 0, s],[s, 0, -s],[-s, 0, -s],[0, -s, 0],])



class Optical_flow_3D:
    def __init__(self, optical_flow):
        self.op_flow = optical_flow
        self.min_op_flow_length = 0.00001
        self.num_frames = len(optical_flow)
        self.vbo_data = self.create_vbo_data()

    def get_vertices(self, frame):
        return self.vbo_data[frame][0]

    def get_colors(self, frame):
        return self.vbo_data[frame][1]

    def get_indices(self, frame):
        return self.vbo_data[frame][2]

    def create_vbo_data(self):
        frames = []
        for frame in tqdm(range(self.num_frames), "Creating VBO data"):
            # Turn y and dy upsidedown
            self.op_flow[frame][:,1] *= -1
            self.op_flow[frame][:,4] *= -1

            # Create arrows at optical flow vectors with length above minimum
            arrows = self.create_arrows(self.op_flow[frame].copy())
            num_arrow_verts = len(arrows)//3
            num_arrows = len(arrows)//arrow_verts.size
            arrow_colors = np.tile(np.array([1, 0, 0]), num_arrow_verts)
            arrow_indices = np.repeat(np.arange(num_arrows), len(arrow_idxs))*arrow_verts.shape[0] + np.tile(arrow_idxs, num_arrows)

            # Create pyramids at optical flow vectors with length below minimum
            pyramids = self.create_pyramids(self.op_flow[frame][:].copy())
            num_pyramid_verts = len(pyramids)//3
            num_pyramids = len(pyramids)//pyramid_verts.size
            colors = np.tile(np.array([.5, .5, 1]), num_pyramid_verts)
            indices = np.repeat(np.arange(num_pyramids), len(pyramid_idxs))*4 + np.tile(pyramid_idxs, num_pyramids)
            indices += max(arrow_indices, default=-1) + 1

            # Combine arrows and pyramids
            frames.append((np.concatenate([arrows, pyramids]),
                           np.concatenate([arrow_colors, colors]),
                           np.concatenate([arrow_indices, indices])))
        return frames

    def create_pyramids(self, op_flow):
        '''
        If the 3D optical flow isn't large enough, just render a pyramid showing
        position of the person in the depth value
        '''
        xyz_length = np.linalg.norm(op_flow[:, 3:], axis=1)
        mask = (xyz_length <= self.min_op_flow_length)
        xyz_length = xyz_length[mask]
        op_flow = op_flow[mask]
        vertices = np.tile(pyramid_verts.copy(), (op_flow.shape[0], 1))
        x = vertices[:,0] + np.repeat(op_flow[:,0], 4)
        y = vertices[:,1] + np.repeat(op_flow[:,1], 4)
        z = vertices[:,2] + np.repeat(op_flow[:,2], 4)
        vertices = np.stack([x,y,z]).T.flatten()
        return vertices


    def create_arrows(self, op_flow):
        # Remove vectors with norm = 0
        xyz_length = np.linalg.norm(op_flow[:, 3:], axis=1)
        mask = (xyz_length > self.min_op_flow_length)
        xyz_length = xyz_length[mask]
        op_flow = op_flow[mask]

        # Amount of arrows in this frame
        num_arrows = op_flow.shape[0]

        # Get rotation angles
        xy_length = np.linalg.norm(op_flow[:, 3:5], axis=1)
        mask = (xy_length == 0)
        z_angles = np.zeros([num_arrows])
        z_angles[mask] = np.radians(90)
        z_angles[~mask] = -np.arccos(op_flow[~mask, 4] / xy_length[~mask])
        x_angles = np.arccos(np.linalg.norm(op_flow[:, 3:5], axis=1) / xyz_length)
        z_angles[op_flow[:,3] < 0] *= -1
        x_angles[op_flow[:,5] < 0] *= -1

        # Perform gaussian smoothing over xyz_length
        # xyz_length = gaussian_filter(xyz_length, 4.0)

        # Get starting vertices
        vertices = np.tile(arrow_verts.copy(), (num_arrows, 1))

        # Scale arrows with size of the vector length
        # vertices *= np.repeat(xyz_length/np.average(xyz_length), len(vertices))[:,np.newaxis]

        # Add vector length to arrow tip
        vertices[8::9,1] += xyz_length*1.5

        # Rotate all points in direction of 3D vector
        x_angles = np.repeat(x_angles,9)
        z_angles = np.repeat(z_angles,9)
        cos_x = np.cos(x_angles)
        sin_x = np.sin(x_angles)
        cos_z = np.cos(z_angles)
        sin_z = np.cos(z_angles)
        y1 = vertices[:, 1]*cos_x - vertices[:, 2]*sin_x
        z1 = vertices[:, 1]*sin_x + vertices[:, 2]*cos_x
        x2 = vertices[:, 0]*cos_z - y1*sin_z
        y2 = vertices[:, 0]*sin_z + y1*cos_z
        x3 = x2 + np.repeat(op_flow[:,0], 9)
        y3 = y2 + np.repeat(op_flow[:,1], 9)
        z3 = z1 + np.repeat(op_flow[:,2], 9)
        vertices = np.stack([x3,y3,z3]).T.flatten()
        return vertices





class OpticalFlowViewer:
    def __init__(self, op_flow):
        self.last_frame_change = time.time()
        self.last_draw = time.time()
        self.frame = 0
        self.draw_fps = 8
        self.fps = 0
        self.last_key   = None
        self.last_key_t = dt.datetime.now()

        # Camera + parameters
        self.camera = Camera()
        self.step_size = step_size0
        self.rotation_angle = rotation_angle0

        # Additional stuff to avoid extra function calls
        self.quadric = gluNewQuadric()

        self.op_flow = Optical_flow_3D(op_flow)
        self.num_frames = self.op_flow.num_frames
        self.buffers = None



    def draw(self):
        '''
        Callback to draw everything in the glut windows
        '''
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        gluLookAt(*self.camera.get_viewing_matrix())

        self.set_fps()
        self.draw_axes()

        # draw objects
        if self.buffers is None:
            self.create_vbo()
        self.draw_vbo()

        glFlush()
        glutSwapBuffers()




    def create_vbo(self):
        '''
        Builds the buffers
        '''
        self.buffers = glGenBuffers(self.op_flow.num_frames * 3)
        for frame in tqdm(range(self.op_flow.num_frames), "Filling in VBO"):
            # Vertex colors
            glBindBuffer(GL_ARRAY_BUFFER, self.buffers[frame*3])
            glBufferData(GL_ARRAY_BUFFER,
                         len(self.op_flow.get_colors(frame))*4,
                         (ctypes.c_float*len(self.op_flow.get_colors(frame)))(*self.op_flow.get_colors(frame)),
                         GL_DYNAMIC_DRAW)
            # Vertex indices
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.buffers[1 + frame*3])
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                         len(self.op_flow.get_indices(frame))*4,
                         (ctypes.c_uint*len(self.op_flow.get_indices(frame)))(*self.op_flow.get_indices(frame)),
                         GL_DYNAMIC_DRAW)
            # Vertex locations
            glBindBuffer(GL_ARRAY_BUFFER, self.buffers[2 + frame*3])
            glBufferData(GL_ARRAY_BUFFER,
                         len(self.op_flow.get_vertices(frame))*4,
                         (ctypes.c_float*len(self.op_flow.get_vertices(frame)))(*self.op_flow.get_vertices(frame)),
                         GL_DYNAMIC_DRAW)




    def draw_vbo(self):
        '''
        Binds the buffer objects for the current frame
        '''
        frame = self.get_frame()
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, self.buffers[2 + frame*3])
        glVertexPointer(3, GL_FLOAT, 0, None)
        glBindBuffer(GL_ARRAY_BUFFER, self.buffers[0 + frame*3])
        glColorPointer(3, GL_FLOAT, 0, None)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.buffers[1 + frame*3])
        glDrawElements(GL_TRIANGLES, len(self.op_flow.get_indices(frame)), GL_UNSIGNED_INT, None)
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)




    def view(self):
        '''
        Main function to create window and register callbacks for displaying
        '''
        # Initialize glut
        glutInit()
        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(width, height)
        glutInitWindowPosition(0, 0)
        glutCreateWindow("Optical Flow Viewer")
        glutMouseFunc(self.mouse_button)
        glutMotionFunc(self.mouse_motion)
        glutDisplayFunc(self.draw)
        glutIdleFunc(self.draw)
        glutReshapeFunc(self.reshape_func)
        glutKeyboardFunc(self.key_pressed)
        glutSpecialFunc(self.sp_key_pressed)

        # Initialize opengl environment
        glClearColor(0., 0., 0., 1.)
        glClearDepth(1.0)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_TEXTURE_2D)
        glShadeModel(GL_SMOOTH)

        # Enter loop - never to return
        glutMainLoop()



    def reshape_func(self, Width, Height):
        '''
        Callback to change the camera on a window resize
        '''
        if Height == 0: Height = 1
        glViewport(0, 0, Width, Height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, float(Width)/float(Height), 0.1, 50.0)




    def sp_key_pressed(self, key, x, y):
        '''
        Arrow keys callback
        '''

        # Accelerate if continuing to press a key
        if key == self.last_key and (dt.datetime.now() - self.last_key_t).total_seconds() < 0.1:
            if self.rotation_angle < 5*rotation_angle0:
                self.rotation_angle = self.rotation_angle * 1.02
        else:
            self.rotation_angle = rotation_angle0

        self.last_key = key
        self.last_key_t = dt.datetime.now()

        if key == GLUT_KEY_LEFT:
            self.camera.rotate_camera_right(self.rotation_angle)
        elif key == GLUT_KEY_RIGHT:
            self.camera.rotate_camera_right(-self.rotation_angle)
        elif key == GLUT_KEY_UP:
            self.camera.rotate_camera_up(self.rotation_angle)
        elif key == GLUT_KEY_DOWN:
            self.camera.rotate_camera_up(-self.rotation_angle)




    def key_pressed(self, key, x, y):
        '''
        Keyboard callback
        '''

        # Accelerate if continuing to press a key
        if key == self.last_key and (dt.datetime.now() - self.last_key_t).total_seconds() < 0.1:
            if self.step_size < step_size0*5:
                self.step_size = self.step_size * 1.1
        else:
            self.step_size = step_size0

        self.last_key = key
        self.last_key_t = dt.datetime.now()

        # Esc or q to exit
        if (key == b'\x1b' or key == b'q'): sys.exit()
        # WASD movement controls
        elif key == b'w': self.camera.move_forward(self.step_size)
        elif key == b'a': self.camera.move_right(-self.step_size)
        elif key == b's': self.camera.move_forward(-self.step_size)
        elif key == b'd': self.camera.move_right(self.step_size)
        # Reset view
        elif key == b'r': self.camera.reset()
        # Change speed
        elif key == b'z': self.draw_fps -= 1 if self.draw_fps > 0 else 0
        elif key == b'x': self.draw_fps += 1




    def mouse_button(self, button, mode, x, y):
        '''
        Mouse click callback
        '''
        if mode == GLUT_DOWN:
            self.mouse_down = True
            self.mouse_start = (x, y)
        else:
            self.mouse_down = False




    def mouse_motion(self, x, y):
        '''
        Mouse motion callback
        '''
        self.camera.rotate_camera_right((x - self.mouse_start[0])*0.001)
        self.camera.rotate_camera_up((y - self.mouse_start[1])*0.001)
        self.mouse_start = (x, y)





    def draw_axes(self):
        '''
        Draws x, y, and z axes
        '''
        glBegin(GL_LINES)
        glColor3f(1, 1, 0)      # x-axis
        glVertex3f(-1000, 0, 0)
        glVertex3f(1000, 0, 0)
        glColor3f(1, 0, 1)      # y-axis
        glVertex3f(0, -1000, 0)
        glVertex3f(0, 1000, 0)
        glColor3f(0, 0, 1)      # z-axis
        glVertex3f(0, 0, -1000)
        glVertex3f(0, 0, 1000)
        glEnd()




    def set_fps(self):
        '''
        Set the window title to the current FPS
        '''
        seconds = time.time()
        if (seconds - self.last_draw >= 1):
            self.last_draw = seconds
            glutSetWindowTitle("{} FPS".format(self.fps))
            self.fps = 0
        self.fps += 1




    def get_frame(self):
        '''
        Return the frame to draw based on the set fps
        '''
        now = time.time()
        if self.draw_fps == 0:
            return self.frame
        if (now - self.last_frame_change) > 1.0/self.draw_fps:
            self.frame = 0 if self.frame == self.num_frames-1 else self.frame + 1
            self.last_frame_change = now
        return self.frame




if __name__ == '__main__':
    # import ntu_rgb
    # dataset = ntu_rgb.NTU()
    # optical_flow = dataset.get_3D_optical_flow(0)

    # Use cached file
    optical_flow = pickle.load(open('cache/op_flow_3D_4.pickle', 'rb'))

    viewer = OpticalFlowViewer(optical_flow)
    viewer.view()
