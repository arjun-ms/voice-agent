# Mykare Voice AI Agent

This is a real-time conversational AI voice agent built for healthcare reception tasks. It allows users to speak directly with an AI, handles back-and-forth exchanges, manages appointments (via SQLite), and presents a seamless web UI with a synchronized voice avatar.

## 🚀 Features
- **Real-Time Voice AI**: Deepgram for STT, Cartesia for TTS, and Google Gemini 2.5 Flash for the LLM.
- **Smart Tool Calling**: Automatically fetches available slots, books appointments, and retrieves user booking history via voice.
- **Visual Call UI**: Shows the agent's current state (Initializing, Listening, Thinking, Speaking) using an orb avatar synced to speech volume.
- **Conversation Summary**: Automatically generates a structured post-call summary using the LLM when the conversation ends.
- **Persistent DB**: SQLite database tracks users, appointments, and call history.

## 🏗️ Architecture
- **Backend (Python)**: Uses `LiveKit Agents` framework. Handles WebRTC connections, STT/TTS routing, and DB operations.
- **Frontend (React / Vite)**: Connects to the LiveKit room via `@livekit/components-react`. Displays tool invocations and live status.

---

## 💻 Local Setup Instructions

### 1. Environment Variables
Rename `.env.example` to `.env` in the root folder and add your keys:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`: [LiveKit Cloud](https://cloud.livekit.io/)
- `GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/)
- `DEEPGRAM_API_KEY`: [Deepgram Console](https://console.deepgram.com/)
- `CARTESIA_API_KEY`: [Cartesia Dashboard](https://play.cartesia.ai/)

### 2. Backend Setup
Requires Python 3.9+
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the backend agent
python voice_agent.py dev
```

### 3. Frontend Setup
Requires Node.js 18+
```bash
cd frontend
npm install
npm run dev
```
Then navigate to `http://localhost:5173`.

---

## ☁️ Deployment

### Backend Deployment (Render, Railway, Fly.io)
A `Dockerfile` is provided in the root directory. You can deploy the backend as a Docker service on any modern hosting platform.
1. Connect your GitHub repository to your platform (e.g., Render).
2. Choose "Docker" as the runtime.
3. Add all environment variables from `.env`.
4. The Dockerfile automatically runs `python backend/voice_agent.py start`.

### Frontend Deployment (Vercel, Netlify)
The frontend is a standard Vite React application.
1. Connect your repository to Vercel/Netlify.
2. Set the Root Directory to `frontend`.
3. The build command will automatically be detected as `npm run build` and output directory as `dist`.
4. Make sure your LiveKit WebSocket URL matches the one configured in the `.env` locally (or in the Vercel dashboard).

---

## 🎥 Demo
Check the root directory of the repository for `screenshot.png`, `screenshot_connected.png`, and `screenshot_summary.png` to view the end-to-end user experience, including tool executions and the post-call summary screen.
