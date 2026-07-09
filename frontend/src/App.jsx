import { Routes, Route } from 'react-router-dom';
import Landing from './pages/Landing.jsx';
import MapDashboard from './pages/MapDashboard.jsx';

export default function App() {
    return (
        <Routes>
           <Route path="/" element={<Landing />} />
           <Route path="/map" element={<MapDashboard />} />
        </Routes>
    );
}
