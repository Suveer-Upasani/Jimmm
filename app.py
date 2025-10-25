import os
import cv2
import numpy as np
import mediapipe as mp
from flask import Flask, render_template, Response, jsonify
from flask_socketio import SocketIO, emit
import base64
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize MediaPipe
mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Global variables
connections = {}
processing_enabled = {}

class MediaPipeVideoStreamTrack(VideoStreamTrack):
    def __init__(self, track, connection_id):
        super().__init__()
        self.track = track
        self.connection_id = connection_id
        self.processing_enabled = True
        self.view_mode = "normal"  # "normal" or "black_background"
        
        # MediaPipe Holistic model
        self.holistic = mp_holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=True,
            smooth_segmentation=True,
            refine_face_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    async def recv(self):
        frame = await self.track.recv()
        
        if not self.processing_enabled:
            return frame

        # Convert to numpy array
        img = frame.to_ndarray(format="bgr24")
        
        try:
            # Process with MediaPipe
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.holistic.process(img_rgb)
            
            # Create output image based on view mode
            if self.view_mode == "black_background":
                output_img = np.zeros_like(img)
            else:
                output_img = img.copy()
            
            # Draw pose landmarks
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    output_img,
                    results.pose_landmarks,
                    mp_holistic.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
                )
            
            # Draw face landmarks
            if results.face_landmarks:
                mp_drawing.draw_landmarks(
                    output_img,
                    results.face_landmarks,
                    mp_holistic.FACEMESH_TESSELATION,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style()
                )
            
            # Draw left hand landmarks
            if results.left_hand_landmarks:
                mp_drawing.draw_landmarks(
                    output_img,
                    results.left_hand_landmarks,
                    mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style()
                )
            
            # Draw right hand landmarks
            if results.right_hand_landmarks:
                mp_drawing.draw_landmarks(
                    output_img,
                    results.right_hand_landmarks,
                    mp_holistic.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style()
                )
            
            # Add border for better visibility
            border_size = 3
            border_color = (0, 255, 0)  # Green border
            output_img = cv2.copyMakeBorder(
                output_img,
                border_size, border_size, border_size, border_size,
                cv2.BORDER_CONSTANT,
                value=border_color
            )
            
            # Convert back to video frame
            processed_frame = VideoFrame.from_ndarray(output_img, format="bgr24")
            processed_frame.pts = frame.pts
            processed_frame.time_base = frame.time_base
            return processed_frame
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return frame

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    if request.sid in connections:
        del connections[request.sid]
    if request.sid in processing_enabled:
        del processing_enabled[request.sid]

@socketio.on('set_view_mode')
def handle_set_view_mode(data):
    connection_id = data.get('connection_id')
    mode = data.get('mode')
    
    if connection_id in connections:
        connections[connection_id]['mediapipe_track'].view_mode = mode
        logger.info(f"View mode set to {mode} for connection {connection_id}")

@socketio.on('start_processing')
def handle_start_processing(data):
    connection_id = data.get('connection_id')
    if connection_id in connections:
        connections[connection_id]['mediapipe_track'].processing_enabled = True
        logger.info(f"Processing started for connection {connection_id}")

@socketio.on('stop_processing')
def handle_stop_processing(data):
    connection_id = data.get('connection_id')
    if connection_id in connections:
        connections[connection_id]['mediapipe_track'].processing_enabled = False
        logger.info(f"Processing stopped for connection {connection_id}")

@socketio.on('offer')
async def handle_offer(data):
    offer = RTCSessionDescription(sdp=data['sdp'], type=data['type'])
    pc = RTCPeerConnection()
    connection_id = str(uuid.uuid4())
    
    # Add local video track (this will be our processed stream)
    mediapipe_track = None
    
    @pc.on("track")
    def on_track(track):
        nonlocal mediapipe_track
        if track.kind == "video":
            mediapipe_track = MediaPipeVideoStreamTrack(track, connection_id)
            pc.addTrack(mediapipe_track)
    
    # Store connection
    connections[connection_id] = {
        'pc': pc,
        'mediapipe_track': mediapipe_track
    }
    
    try:
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        emit('answer', {
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type,
            'connection_id': connection_id
        })
        
    except Exception as e:
        logger.error(f"Error handling offer: {e}")
        emit('error', {'error': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5005, debug=True, allow_unsafe_werkzeug=True)