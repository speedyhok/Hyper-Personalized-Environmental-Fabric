// static/dashboard.js

let socket = null;
let signalsChart = null;
let circumplexCanvas = null;
let circumplexCtx = null;

// Target coordinates for CSM state dot (Valence & Arousal)
let currentValence = 0.0;
let currentArousal = 0.0;
let drawValence = 0.0;
let drawArousal = 0.0;
let predictedPath = [];

// YouTube Sensory Player API variables
let lastLogs = [];
let ytPlayer = null;
let ytPlayerReady = false;
let activeYTMode = "Focus";

const playlistTracks = {
    "Focus": [
        { id: "lTRiuFIWV54", name: "Chillhop 1 A.M. Study Session" },
        { id: "5yx6Gygb9ps", name: "Chillhop Essentials Beats" },
        { id: "lTRiuFIWV54", name: "Lofi Focus Study Session" }
    ],
    "Calm": [
        { id: "2OEL4P1Rz04", name: "Beautiful Stress Relief Music" },
        { id: "H14bBuluRyQ", name: "Soothing Meditation Ambient" },
        { id: "mPZkdNFkNps", name: "Gentle Rain on Window" }
    ],
    "Stress": [
        { id: "8-xIap4U9X0", name: "Liquid Mind Deep Relaxation" },
        { id: "Uqyco8_X7pU", name: "Tibetan Singing Bowls" },
        { id: "2OEL4P1Rz04", name: "Calm Valley Stress Relief" }
    ]
};




// 3D Room state
let room3d = null;


// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
    initChart();
    initRoom3D();
    initCircumplex();
    connectWebSocket();
    animateCircumplex();

    
    // Force a chart resize on next paint after the DOM is ready
    // so Chart.js has real container dimensions (not 0×0)
    requestAnimationFrame(() => {
        if (signalsChart) {
            signalsChart.resize();
            signalsChart.update();
        }
    });
    
    // Load hardware config if set
    fetch("/api/config/hardware")
        .then(res => res.json())
        .then(data => {
            if (data.hue_ip) {
                document.getElementById("config-hue-ip").value = data.hue_ip;
            }
            if (data.hue_key_configured) {
                document.getElementById("config-hue-key").placeholder = "•••••••••••••••• (Active)";
            }
        })
        .catch(err => console.error("Failed to load hardware configs:", err));

});


// 1. Initialize multi-axis Chart.js for real-time wave visualization

function initChart() {
    const ctx = document.getElementById("signalsChart").getContext("2d");
    
    // Create soft placeholder waveform so the chart is visibly rendered from the start
    const sampleCount = 100;
    const labels = Array.from({length: sampleCount}, (_, i) => "");
    const placeholderEEG = Array.from({length: sampleCount}, (_, i) => Math.sin(i * 0.2) * 0.3);
    const placeholderPPG = Array.from({length: sampleCount}, (_, i) => Math.sin(i * 0.15 + 1) * 0.2);
    const placeholderGSR = Array.from({length: sampleCount}, (_, i) => Math.sin(i * 0.1 + 2) * 0.1);

    signalsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'EEG Alpha/Beta composite',
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.05)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    data: placeholderEEG,
                    yAxisID: 'y-eeg'
                },
                {
                    label: 'PPG Pulse Waveform',
                    borderColor: '#0ea5e9',
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    data: placeholderPPG,
                    yAxisID: 'y-ppg'
                },
                {
                    label: 'GSR Electrodermal Level',
                    borderColor: '#d97706',
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    data: placeholderGSR,
                    yAxisID: 'y-gsr'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    display: false
                },
                'y-eeg': {
                    type: 'linear',
                    position: 'left',
                    grid: { color: 'rgba(0, 0, 0, 0.05)' },
                    ticks: { display: false }
                },
                'y-ppg': {
                    type: 'linear',
                    position: 'right',
                    grid: { display: false },
                    ticks: { display: false }
                },
                'y-gsr': {
                    type: 'linear',
                    position: 'right',
                    grid: { display: false },
                    ticks: { display: false }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#475569',
                        font: { size: 11, family: 'Inter' }
                    }
                }
            }
        }
    });
}


// ============================================================
// ============================================================
// 3D ROOM VISUALIZATION  (Three.js - High Aesthetic Upgrade)
// ============================================================
let underDeskLight = null; // additional mood light for back wall wash
let behindSofaLight = null; // wall wash behind the sofa

function initRoom3D() {
    const canvas = document.getElementById('room3d-canvas');
    if (!canvas || typeof THREE === 'undefined') return;

    const W = canvas.clientWidth  || 900;
    const H = canvas.clientHeight || 380;

    // --- Renderer ---
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setSize(W, H);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;

    // --- Scene ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f1d); // deep premium midnight base
    scene.fog = new THREE.FogExp2(0x0a0f1d, 0.03);

    // --- Camera (Premium 3/4 Corner Perspective) ---
    const camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 50);
    camera.position.set(4.8, 3.2, 5.8);
    camera.lookAt(-0.3, 1.2, -1.1);

    // --- Materials (Premium Design Palette) ---
    const floorMat  = new THREE.MeshStandardMaterial({ color: 0xdfd3c3, roughness: 0.6, metalness: 0.05 }); // Light Oak
    const wallMat   = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.95 }); // Slate Dark feature wall
    const wallSideMat = new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.95 }); // Accent walls
    const ceilMat   = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 1.0 });
    const woodMat   = new THREE.MeshStandardMaterial({ color: 0x452a1e, roughness: 0.7 }); // Premium Dark Walnut
    const marbleMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.1, metalness: 0.15 }); // White Carrara marble
    const brassMat  = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.2, metalness: 0.9 }); // Brushed Gold/Brass
    const darkMat   = new THREE.MeshStandardMaterial({ color: 0x18181b, roughness: 0.5, metalness: 0.3 }); // Matte Black
    const screenMat = new THREE.MeshStandardMaterial({ color: 0x090d16, emissive: 0x0c1424, emissiveIntensity: 1.2, roughness: 0.2 }); // Curved OLED display
    const plantMat  = new THREE.MeshStandardMaterial({ color: 0x15803d, roughness: 0.85, side: THREE.DoubleSide }); // Fiddle-leaf green
    const potMat    = new THREE.MeshStandardMaterial({ color: 0xf3f4f6, roughness: 0.4 }); // White Ceramic planter
    const sofaMat   = new THREE.MeshStandardMaterial({ color: 0xf5f5f4, roughness: 0.9 }); // Cream Bouclé fabric
    const rugMat    = new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness: 1.0 }); // Soft woven rug
    const diffMat   = new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.92, roughness: 0.1 }); // Opal glass diffuser
    const globeMat   = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 1.2, roughness: 0.1 }); // Light globe

    // --- Room Geometry ---
    // Floor
    const floor = new THREE.Mesh(new THREE.BoxGeometry(10, 0.1, 10), floorMat);
    floor.position.set(0, -0.05, 0); floor.receiveShadow = true;
    scene.add(floor);

    // Woven Rug (Circular)
    const rug = new THREE.Mesh(new THREE.CylinderGeometry(2.3, 2.3, 0.01, 32), rugMat);
    rug.position.set(-0.8, 0.005, -1.0); rug.receiveShadow = true;
    scene.add(rug);

    // Back wall
    const backWall = new THREE.Mesh(new THREE.BoxGeometry(10, 5, 0.1), wallMat);
    backWall.position.set(0, 2.5, -5); backWall.receiveShadow = true;
    scene.add(backWall);

    // Left wall
    const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.1, 5, 10), wallSideMat);
    leftWall.position.set(-5, 2.5, 0); leftWall.receiveShadow = true;
    scene.add(leftWall);

    // Right wall (short wall to allow open camera look)
    const rightWall = new THREE.Mesh(new THREE.BoxGeometry(0.1, 5, 10), wallSideMat);
    rightWall.position.set(5, 2.5, 0); rightWall.receiveShadow = true;
    scene.add(rightWall);

    // Ceiling
    const ceil = new THREE.Mesh(new THREE.BoxGeometry(10, 0.1, 10), ceilMat);
    ceil.position.set(0, 5.05, 0);
    scene.add(ceil);

    // --- Floor-to-Ceiling Window (back-left wall, sleek dark frame) ---
    const winFrame = new THREE.Mesh(new THREE.BoxGeometry(2.4, 3.8, 0.12), darkMat);
    winFrame.position.set(-2.8, 1.9, -4.94);
    scene.add(winFrame);

    const windowGlass = new THREE.Mesh(new THREE.BoxGeometry(2.2, 3.6, 0.02),
        new THREE.MeshStandardMaterial({ color: 0x1e293b, transparent: true, opacity: 0.2, roughness: 0.05, metalness: 0.1 }));
    windowGlass.position.set(-2.8, 1.9, -4.93);
    scene.add(windowGlass);

    // Dynamic Outside window lighting (ambient sky glow)
    const windowLight = new THREE.RectAreaLight(0x38bdf8, 4.0, 2.2, 3.6);
    windowLight.position.set(-2.8, 1.9, -4.8);
    windowLight.lookAt(-2.8, 1.9, 0);
    scene.add(windowLight);

    // --- Modern Flat Painting Frame (CanvasTexture - Fixes 3D overlap distortion) ---
    const frameWidth = 1.6;
    const frameHeight = 2.2;
    const frameMesh = new THREE.Mesh(new THREE.BoxGeometry(frameWidth, frameHeight, 0.06), brassMat);
    frameMesh.position.set(1.4, 2.7, -4.94); frameMesh.castShadow = true;
    scene.add(frameMesh);

    // Draw the abstract painting dynamically onto a 2D canvas texture
    const artCanvas = document.createElement('canvas');
    artCanvas.width = 512;
    artCanvas.height = 704;
    const artCtx = artCanvas.getContext('2d');
    
    // Abstract Art Background
    artCtx.fillStyle = '#faf8f5';
    artCtx.fillRect(0, 0, 512, 704);
    
    // Abstract overlapping circles & lines (sleek modern gallery poster style)
    artCtx.fillStyle = '#ccd5ae';
    artCtx.beginPath(); artCtx.arc(200, 280, 160, 0, Math.PI * 2); artCtx.fill();
    
    artCtx.fillStyle = '#d4a373';
    artCtx.beginPath(); artCtx.arc(320, 420, 140, 0, Math.PI * 2); artCtx.fill();
    
    artCtx.fillStyle = '#b3c5af';
    artCtx.beginPath(); artCtx.arc(240, 500, 90, 0, Math.PI * 2); artCtx.fill();
    
    artCtx.strokeStyle = '#1e293b';
    artCtx.lineWidth = 6;
    artCtx.beginPath(); artCtx.arc(256, 352, 220, 0, Math.PI, true); artCtx.stroke();
    
    artCtx.fillStyle = '#e9d8a6';
    artCtx.beginPath(); artCtx.arc(256, 352, 30, 0, Math.PI * 2); artCtx.fill();

    const artTexture = new THREE.CanvasTexture(artCanvas);
    const painting = new THREE.Mesh(
        new THREE.PlaneGeometry(frameWidth - 0.08, frameHeight - 0.08),
        new THREE.MeshStandardMaterial({ map: artTexture, roughness: 0.9 })
    );
    painting.position.set(1.4, 2.7, -4.9);
    scene.add(painting);

    // --- Premium Floating Marble & Brass Desk ---
    const deskTop = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.08, 0.9), marbleMat);
    deskTop.position.set(1.4, 1.1, -3.6); deskTop.castShadow = true; deskTop.receiveShadow = true;
    scene.add(deskTop);

    // Sleek V-shaped brass desk legs
    [-1.0, 1.0].forEach(x => {
        const legGroup = new THREE.Group();
        legGroup.position.set(1.4 + x, 0.55, -3.6);

        const legL = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.1, 8), brassMat);
        legL.rotation.z = 0.2; legL.castShadow = true;
        const legR = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.1, 8), brassMat);
        legR.rotation.z = -0.2; legR.castShadow = true;

        legGroup.add(legL); legGroup.add(legR);
        scene.add(legGroup);
    });

    // Curved Ultra-Wide Monitor
    const monStand = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.45, 8), brassMat);
    monStand.position.set(1.4, 1.3, -3.85); monStand.castShadow = true;
    scene.add(monStand);

    const monScreen = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.6, 0.04), screenMat);
    monScreen.position.set(1.4, 1.62, -3.85); monScreen.castShadow = true;
    scene.add(monScreen);

    // Sleek Chic Office Chair
    const chairBase = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.06, 16), darkMat);
    chairBase.position.set(1.4, 0.4, -2.8); chairBase.castShadow = true;
    scene.add(chairBase);
    const chairStem = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.35, 8), brassMat);
    chairStem.position.set(1.4, 0.6, -2.8);
    scene.add(chairStem);
    const chairSeat = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.08, 0.48), woodMat);
    chairSeat.position.set(1.4, 0.78, -2.8); chairSeat.castShadow = true;
    scene.add(chairSeat);
    const chairCushion = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.06, 0.44),
        new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 }));
    chairCushion.position.set(1.4, 0.85, -2.8);
    scene.add(chairCushion);
    const chairBack = new THREE.Mesh(new THREE.BoxGeometry(0.48, 0.45, 0.06), woodMat);
    chairBack.position.set(1.4, 1.1, -3.02); chairBack.rotation.x = -0.1; chairBack.castShadow = true;
    scene.add(chairBack);

    // Minimalist keyboard and trackpad
    const keyboard = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.02, 0.22), darkMat);
    keyboard.position.set(1.4, 1.15, -3.4);
    scene.add(keyboard);

    // --- Premium Bookshelf (ladder frame) ---
    const LFrameL = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.8, 8), darkMat);
    LFrameL.position.set(4.6, 1.4, -2.2); LFrameL.rotation.z = -0.06;
    scene.add(LFrameL);
    const LFrameR = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 2.8, 8), darkMat);
    LFrameR.position.set(4.6, 1.4, -3.8); LFrameR.rotation.z = -0.06;
    scene.add(LFrameR);

    // Shelves and books
    [0.6, 1.2, 1.8, 2.4].forEach((y, i) => {
        const shelf = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.03, 1.8), woodMat);
        shelf.position.set(4.5 - i*0.03, y, -3.0); shelf.castShadow = true;
        scene.add(shelf);

        // Books stacked and leaning
        const bookColors = [0x50727b, 0xa25772, 0xef8052, 0x9fb5a3, 0x3a4f7c];
        let bz = -3.7 + i*0.1;
        for (let b = 0; b < 6; b++) {
            const h = 0.24 + Math.random() * 0.12;
            const w = 0.16 + Math.random() * 0.08;
            const book = new THREE.Mesh(new THREE.BoxGeometry(0.28, h, w),
                new THREE.MeshStandardMaterial({ color: bookColors[b % bookColors.length], roughness: 0.8 }));
            book.position.set(4.45 - i*0.03, y + h/2, bz);
            book.castShadow = true;
            if (b === 5) {
                book.rotation.z = 0.22; // leaning book!
                book.position.y -= 0.02;
                book.position.x -= 0.02;
            }
            bz += 0.26;
            scene.add(book);
        }
    });

    // --- High-End Lounge Sofa (Bouclé style, left-front) ---
    const sofaBase = new THREE.Mesh(new THREE.BoxGeometry(2.3, 0.32, 1.0), sofaMat);
    sofaBase.position.set(-2.0, 0.22, -2.4); sofaBase.castShadow = true; sofaBase.receiveShadow = true;
    scene.add(sofaBase);

    // Thick bolster arm cushions
    [-1.0, 1.0].forEach(x => {
        const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.9, 16), sofaMat);
        arm.rotation.x = Math.PI / 2;
        arm.position.set(-2.0 + x*1.15, 0.44, -2.4); arm.castShadow = true;
        scene.add(arm);
    });

    // Sofa backrest
    const sofaBack = new THREE.Mesh(new THREE.BoxGeometry(2.3, 0.65, 0.22), sofaMat);
    sofaBack.position.set(-2.0, 0.65, -2.9); sofaBack.castShadow = true;
    scene.add(sofaBack);

    // Pillows
    const p1 = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.45, 0.18), new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.9 })); // Gold pillow
    p1.position.set(-1.4, 0.5, -2.75); p1.rotation.y = 0.2; p1.rotation.z = 0.1;
    scene.add(p1);
    const p2 = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.4, 0.16), new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.95 })); // Dark blue pillow
    p2.position.set(-2.4, 0.5, -2.75); p2.rotation.y = -0.15;
    scene.add(p2);

    // --- Ceramic Planter & Leafy Fiddle-Leaf Fig Plant ---
    const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.18, 0.55, 16), potMat);
    pot.position.set(-4.0, 0.275, -4.0); pot.castShadow = true;
    scene.add(pot);

    const soil = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.05, 12), darkMat);
    soil.position.set(-4.0, 0.54, -4.0);
    scene.add(soil);

    // Branching stems and rotated plane leaves (looks far better than a simple ball)
    const plantGroup = new THREE.Group();
    plantGroup.position.set(-4.0, 0.55, -4.0);

    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.03, 1.4, 8), woodMat);
    trunk.position.set(0, 0.7, 0); trunk.castShadow = true;
    plantGroup.add(trunk);

    // Create 9 custom leaves at varying positions
    for (let l = 0; l < 9; l++) {
        const branchY = 0.4 + l*0.12;
        const scale = 0.25 + l*0.03;
        const leaf = new THREE.Mesh(new THREE.SphereGeometry(scale, 8, 8), plantMat);
        leaf.scale.set(1.0, 0.15, 1.6);
        leaf.position.set(
            Math.sin(l * 1.5) * 0.15,
            branchY,
            Math.cos(l * 1.5) * 0.15
        );
        leaf.rotation.x = 0.4 + Math.random()*0.3;
        leaf.rotation.y = l * 1.5;
        leaf.rotation.z = 0.3;
        leaf.castShadow = true;
        plantGroup.add(leaf);
    }
    scene.add(plantGroup);

    // --- Scent Diffuser (Opal Teardrop Dome, on desk) ---
    const diff = new THREE.Group();
    diff.position.set(2.2, 1.14, -3.6);

    const dBase = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.05, 16), brassMat);
    dBase.position.y = 0.025;
    diff.add(dBase);

    const dDome = new THREE.Mesh(new THREE.SphereGeometry(0.11, 24, 24, 0, Math.PI * 2, 0, Math.PI * 0.75), diffMat);
    dDome.position.y = 0.12;
    diff.add(dDome);

    scene.add(diff);

    // --- Premium Spherical Ambient Pendant Ceiling Lamp ---
    // Added black cable cord and brass cap to remove floating illusion
    const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 1.4, 8), darkMat);
    cord.position.set(0, 4.35, -2.0);
    scene.add(cord);

    const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.06, 12), brassMat);
    collar.position.set(0, 3.55, -2.0);
    scene.add(collar);

    const globe = new THREE.Mesh(new THREE.SphereGeometry(0.24, 32, 32), globeMat);
    globe.position.set(0, 3.32, -2.0);
    scene.add(globe);

    // --- Minimalist Studio Monitor Speaker (on desk, left) ---
    const spkr = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.32, 0.18), darkMat);
    spkr.position.set(0.4, 1.3, -3.7); spkr.castShadow = true;
    scene.add(spkr);
    const spkrCone = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.02, 12), brassMat);
    spkrCone.rotation.x = Math.PI / 2;
    spkrCone.position.set(0.4, 1.25, -3.6);
    scene.add(spkrCone);

    // --- Lights (Coordinated Multi-Source Setup) ---
    // Soft overhead ambient light
    const ambient = new THREE.AmbientLight(0x0f172a, 0.25);
    scene.add(ambient);

    // Ceiling Pendant Point Light (the main dynamic light)
    const ceilLight = new THREE.PointLight(0xffd89b, 2.8, 12);
    ceilLight.position.set(0, 3.2, -2.0);
    ceilLight.castShadow = true;
    ceilLight.shadow.mapSize.width  = 1024;
    ceilLight.shadow.mapSize.height = 1024;
    ceilLight.shadow.bias = -0.001;
    scene.add(ceilLight);

    // Under-Desk LED mood wash light (creates a beautiful dynamic wash on the back feature wall)
    underDeskLight = new THREE.PointLight(0xffd89b, 2.0, 5);
    underDeskLight.position.set(1.4, 1.02, -3.95);
    scene.add(underDeskLight);

    // Behind-Sofa LED wall wash light (secondary dynamic mood source)
    behindSofaLight = new THREE.PointLight(0xffd89b, 1.8, 4.5);
    behindSofaLight.position.set(-2.0, 0.45, -2.95);
    scene.add(behindSofaLight);

    // --- Swirling Scent Mist Particles ---
    const PARTICLE_COUNT = 80;
    const pPositions = new Float32Array(PARTICLE_COUNT * 3);
    const pVels = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
        pPositions[i*3]   = 2.2;
        pPositions[i*3+1] = 1.3 + Math.random() * 1.5;
        pPositions[i*3+2] = -3.6;
        pVels.push({
            angle: Math.random() * Math.PI * 2,
            speed: 0.008 + Math.random()*0.008,
            radius: 0.02 + Math.random()*0.05,
            vx: 0,
            vy: 0.006 + Math.random()*0.005,
            life: Math.random()
        });
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
    const pMat = new THREE.PointsMaterial({ color: 0xc4b5fd, size: 0.04, transparent: true, opacity: 0.7, depthWrite: false, blending: THREE.AdditiveBlending });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    // --- Sound rings (expand from speaker) ---
    const rings = [];
    for (let r = 0; r < 4; r++) {
        const rGeo = new THREE.RingGeometry(0.01, 0.035, 24);
        const rMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.0, side: THREE.DoubleSide });
        const ring = new THREE.Mesh(rGeo, rMat);
        ring.position.set(0.4, 1.25, -3.58);
        ring.rotation.y = 0; // face camera diagonal
        ring.userData = { phase: r * 0.25, scale: 0.01 };
        scene.add(ring);
        rings.push(ring);
    }

    // --- State targets for smooth lerping ---
    let targetLightColor = new THREE.Color(0xffd89b);
    let targetLightIntensity = 2.8;
    let targetParticleColor = new THREE.Color(0xc4b5fd);
    let soundActive = false;
    let scentIntensity = 0.55;
    let clock = new THREE.Clock();

    // Resize handler
    function onResize() {
        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', onResize);

    // --- Render Loop (Smooth animations) ---
    function animate() {
        requestAnimationFrame(animate);
        const t = clock.getElapsedTime();

        // 1. Lerp main pendant light, under-desk light, behind-sofa light and ambient color
        ceilLight.color.lerp(targetLightColor, 0.025);
        underDeskLight.color.lerp(targetLightColor, 0.025);
        behindSofaLight.color.lerp(targetLightColor, 0.025);
        ambient.color.lerp(targetLightColor, 0.025);
        globe.material.emissive.lerp(targetLightColor, 0.025);
        globe.material.color.lerp(targetLightColor, 0.025); // Globe body tint
        
        ceilLight.intensity += (targetLightIntensity - ceilLight.intensity) * 0.025;
        underDeskLight.intensity += (targetLightIntensity*0.85 - underDeskLight.intensity) * 0.025;
        behindSofaLight.intensity += (targetLightIntensity*0.75 - behindSofaLight.intensity) * 0.025;

        // 2. Swirling scent mist (helical path animation)
        const pos = particles.geometry.attributes.position;
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            pVels[i].life += 0.005;
            pVels[i].angle += pVels[i].speed;
            
            // Helix radius expands as mist goes up
            const r = pVels[i].radius * (1.0 + (pos.array[i*3+1] - 1.3)*2.5);
            
            pos.array[i*3]   = 2.2 + Math.sin(pVels[i].angle + t*2) * r;
            pos.array[i*3+1] += pVels[i].vy * scentIntensity;
            pos.array[i*3+2] = -3.6 + Math.cos(pVels[i].angle + t*2) * r;
            
            if (pVels[i].life > 1.0 || pos.array[i*3+1] > 2.8) {
                pos.array[i*3]   = 2.2;
                pos.array[i*3+1] = 1.25;
                pos.array[i*3+2] = -3.6;
                pVels[i].life = 0;
                pVels[i].angle = Math.random() * Math.PI * 2;
            }
        }
        pos.needsUpdate = true;
        pMat.color.lerp(targetParticleColor, 0.05);

        // 3. Sound rings pulsing
        rings.forEach((ring) => {
            ring.userData.phase += soundActive ? 0.015 : 0.005;
            const p = ring.userData.phase % 1.0;
            const sc = 0.1 + p * 3.5;
            ring.scale.set(sc, sc, sc);
            ring.material.opacity = soundActive
                ? Math.max(0, 0.7 * (1.0 - p))
                : Math.max(0, 0.1 * (1.0 - p));
        });

        // 4. Smooth floating camera sway
        camera.position.x = 4.8 + Math.sin(t * 0.08) * 0.18;
        camera.position.y = 3.2 + Math.sin(t * 0.12) * 0.06;
        camera.lookAt(-0.3, 1.2, -1.1);

        renderer.render(scene, camera);
    }
    animate();

    // Store references
    room3d = {
        ceilLight,
        underDeskLight,
        behindSofaLight,
        ambient,
        windowLight,
        scene,
        pMat,
        particles,
        rings,
        update(rgb, lux, soundOn, scentName, tempC) {
            const r = rgb[0]/255, g = rgb[1]/255, b = rgb[2]/255;
            targetLightColor.setRGB(r, g, b);
            
            // Scaled intensity
            targetLightIntensity = 1.2 + (lux / 400) * 2.2;
            soundActive = soundOn;
            
            // Adjust scent intensity
            scentIntensity = 0.4 + Math.random() * 0.4;
            
            // Set particle color based on scent
            if (scentName && scentName.toLowerCase().includes('lemon')) targetParticleColor.set(0xfde68a);
            else if (scentName && scentName.toLowerCase().includes('cedar')) targetParticleColor.set(0xa78f6d);
            else if (scentName && scentName.toLowerCase().includes('pine')) targetParticleColor.set(0x86efac);
            else if (scentName && scentName.toLowerCase().includes('jasmine')) targetParticleColor.set(0xfbcfe8);
            else targetParticleColor.set(0xc4b5fd); // Lavender calming

            // Dynamic Window Sky Glow: changes color with outdoor weather temperature
            // Cold temperatures: crisp light blue. Warm/hot temperatures: summer golden sunset tint.
            const wTemp = Math.max(0, Math.min(1, (tempC - 10) / 30));
            // Lerp window light between blue (0.2, 0.6, 0.95) and warm gold (0.95, 0.6, 0.2)
            const wr = 0.2 + wTemp * 0.75;
            const wg = 0.6;
            const wb = 0.95 - wTemp * 0.75;
            windowLight.color.setRGB(wr, wg, wb);
            
            // Screen content reacts to the mood light
            screenMat.emissive.setRGB(r*0.12, g*0.12, b*0.2);
        }
    };
}


// Called every WebSocket tick to sync room with live data
function updateRoom3D(data) {
    if (!room3d) return;
    try {
        const rgb     = data.synthesis.light.rgb;
        const lux     = data.synthesis.light.lux  || 200;
        const scent   = data.synthesis.olfactory   || {};
        const scentName = scent.scent || '';
        const soundOn = data.synthesis.sound && data.synthesis.sound.carrier_frequency > 0;
        const tempC   = data.context ? (data.context.outdoor_weather || '').match(/([\d.]+)°C/)?.[1] : 22;
        room3d.update(rgb, lux, soundOn, scentName, parseFloat(tempC) || 22);

        // Update header labels
        const lightLabel = data.synthesis.light.lighting_label || '--';
        const scentLabel = scentName || '--';
        const soundLabel = data.synthesis.sound ? `${data.synthesis.sound.binaural_offset} Hz` : '--';
        const tempLabel  = data.environment ? `${data.environment.temp.toFixed(1)}°C` : '--';
        const rl = document.getElementById('room-light-label');
        const rs = document.getElementById('room-scent-label');
        const rso = document.getElementById('room-sound-label');
        const rt = document.getElementById('room-temp-label');
        if (rl) rl.textContent = lightLabel;
        if (rs) rs.textContent = scentLabel;
        if (rso) rso.textContent = soundLabel;
        if (rt) rt.textContent = tempLabel;
    } catch(e) { /* silent */ }
}


// 2. Initialize Circumplex Grid Canvas
function initCircumplex() {
    circumplexCanvas = document.getElementById("circumplexCanvas");
    circumplexCtx = circumplexCanvas.getContext("2d");
}

// Draw the circumplex model space
function drawCircumplexSpace() {
    const ctx = circumplexCtx;
    const w = circumplexCanvas.width;
    const h = circumplexCanvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const r = w / 2 - 10;
    
    ctx.clearRect(0, 0, w, h);
    
    // Draw grid background concentric circles
    ctx.strokeStyle = "rgba(0, 0, 0, 0.08)";
    ctx.lineWidth = 1;
    for (let radius = r / 3; radius <= r; radius += r / 3) {
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
        ctx.stroke();
    }
    
    // Draw axes
    ctx.beginPath();
    ctx.moveTo(cx, 10);
    ctx.lineTo(cx, h - 10);
    ctx.moveTo(10, cy);
    ctx.lineTo(w - 10, cy);
    ctx.stroke();

    // Draw quadrant division indicators
    ctx.fillStyle = "rgba(15, 23, 42, 0.35)";
    ctx.font = "bold 9px Inter";
    
    // Draw current user coordinate (interpolated for smooth sliding)
    // Map valence/arousal from [-1, 1] to canvas coordinates
    // Valence = X axis, Arousal = Y axis (inverted on screen Y)
    const dotX = cx + drawValence * r;
    const dotY = cy - drawArousal * r;
    
    // Draw predicted trajectory path (Phase 2 projection)
    if (predictedPath && predictedPath.length > 0) {
        ctx.strokeStyle = "rgba(14, 165, 233, 0.6)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        
        ctx.moveTo(dotX, dotY);
        predictedPath.forEach(pt => {
            const px = cx + pt[0] * r;
            const py = cy - pt[1] * r;
            ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.setLineDash([]); // Reset
        
        // Draw a tiny predicted target endpoint dot
        const finalPt = predictedPath[predictedPath.length - 1];
        ctx.fillStyle = "rgba(14, 165, 233, 0.9)";
        ctx.beginPath();
        ctx.arc(cx + finalPt[0] * r, cy - finalPt[1] * r, 4, 0, 2 * Math.PI);
        ctx.fill();
    }
    
    // Draw halo glow around current state
    const grad = ctx.createRadialGradient(dotX, dotY, 2, dotX, dotY, 20);
    grad.addColorStop(0, 'rgba(99, 102, 241, 0.6)');
    grad.addColorStop(0.5, 'rgba(14, 165, 233, 0.2)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(dotX, dotY, 20, 0, 2 * Math.PI);
    ctx.fill();
    
    // Draw target dot
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = "#6366f1";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(dotX, dotY, 7, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
}

// Smooth anim loop for the target coordinate marker
function animateCircumplex() {
    // Linear interpolation (lerp) towards target coordinate for fluid motions
    drawValence += (currentValence - drawValence) * 0.1;
    drawArousal += (currentArousal - drawArousal) * 0.1;
    
    drawCircumplexSpace();
    requestAnimationFrame(animateCircumplex);
}

// 3. Setup WebSocket Connection
function connectWebSocket() {
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);
    
    const statusBadge = document.getElementById("ws-status");
    
    socket.onopen = () => {
        statusBadge.textContent = "Connected";
        statusBadge.className = "status-badge connected";
    };
    
    socket.onclose = () => {
        statusBadge.textContent = "Disconnected";
        statusBadge.className = "status-badge disconnected";
        // Retry connection in 3 seconds
        setTimeout(connectWebSocket, 3000);
    };
    
    socket.onerror = () => {
        statusBadge.textContent = "Error";
        statusBadge.className = "status-badge disconnected";
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateUI(data);
    };
}

// 4. Update DOM Nodes with real-time payload
function updateUI(data) {
    // Wearable connection status
    const wearBadge = document.getElementById("wearable-status");
    if (data.wearable && data.wearable.seconds_since_update < 45.0) {
        const src = data.wearable.source || "Active";
        wearBadge.textContent = `Connected (${src})`;
        wearBadge.className = "status-badge connected";
    } else {
        wearBadge.textContent = "Disconnected";
        wearBadge.className = "status-badge disconnected";
    }
    
    // Hue connection status
    const hueBadge = document.getElementById("hue-status");
    if (data.hue_connected) {
        hueBadge.textContent = "Connected";
        hueBadge.className = "status-badge connected";
    } else {
        hueBadge.textContent = "Disconnected";
        hueBadge.className = "status-badge disconnected";
    }
    
    // Home Assistant connection status
    const haBadge = document.getElementById("ha-status");
    if (data.ha_connected) {
        haBadge.textContent = "Connected";
        haBadge.className = "status-badge connected";
    } else {
        haBadge.textContent = "Disconnected";
        haBadge.className = "status-badge disconnected";
    }

    // Biometric metrics
    document.getElementById("hr-val").textContent = Math.round(data.features.heart_rate);
    document.getElementById("hrv-val").textContent = Math.round(data.features.hrv_rmssd);
    document.getElementById("gsr-val").textContent = data.features.gsr_phasic.toFixed(2);
    document.getElementById("load-val").textContent = Math.round(data.csm.cognitive_load * 100);
    
    // CSM coordinates
    currentValence = data.csm.valence;
    currentArousal = data.csm.arousal;
    document.getElementById("state-label").textContent = data.csm.state_label;
    
    // Environmental properties
    document.getElementById("env-temp").textContent = data.environment.temp.toFixed(1);
    document.getElementById("env-light").textContent = Math.round(data.environment.light);
    document.getElementById("env-noise").textContent = Math.round(data.environment.noise);
    
    // Context status
    document.getElementById("circadian-val").textContent = data.context.circadian_phase;
    document.getElementById("next-event-val").textContent = data.context.next_event;
    // Show location + condition in header weather stat
    const locLabel = data.context.location && data.context.location !== 'Not set'
        ? `${data.context.outdoor_weather} · ${data.context.location}`
        : data.context.outdoor_weather;
    document.getElementById("weather-val").textContent = locLabel;
    
    // Closed Loop recommendations
    document.getElementById("rec-light").textContent = data.recommendations.light;
    document.getElementById("rec-sound").textContent = data.recommendations.sound;
    document.getElementById("rec-temp").textContent = data.recommendations.temp;
    document.getElementById("rec-scent").textContent = data.recommendations.scent;

    // Phase 3 YouTube Sensory Music synchronization
    syncSensoryMusic(data.csm, data.rl_policy);
    
    // Dynamic Ambient Lighting Glow
    const rgb = data.synthesis.light.rgb;
    document.body.style.backgroundImage = `radial-gradient(circle at 10% 10%, rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0.05) 0%, rgba(255,255,255,0) 70%), radial-gradient(circle at 90% 90%, rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, 0.02) 0%, rgba(255,255,255,0) 70%)`;

    // Sync 3D room scene with current synthesis state
    updateRoom3D(data);

    // RL Policy dashboard bindings
    document.getElementById("rl-action-val").textContent = data.rl_policy.action;
    document.getElementById("rl-reward-val").textContent = data.rl_policy.reward.toFixed(3);
    
    // Toggle active status for RL Optimizer target buttons
    const focusBtn = document.getElementById("target-focus-btn");
    const calmBtn = document.getElementById("target-calm-btn");
    if (data.rl_policy.target_state === "Focus") {
        focusBtn.className = "btn btn-success";
        calmBtn.className = "btn btn-outline";
    } else {
        focusBtn.className = "btn btn-outline";
        calmBtn.className = "btn btn-success";
    }
    
    
    // Phase 2 Predictions & Causal Attribution binding
    predictedPath = data.csm_predictions.interpolated_path;
    
    const workloadPct = data.causal_attribution.workload;
    const envPct = data.causal_attribution.environment;
    const physPct = data.causal_attribution.physiology;
    
    document.getElementById("attr-workload-val").textContent = `${workloadPct}%`;
    document.getElementById("attr-workload").style.width = `${workloadPct}%`;
    
    document.getElementById("attr-env-val").textContent = `${envPct}%`;
    document.getElementById("attr-env").style.width = `${envPct}%`;
    
    document.getElementById("attr-phys-val").textContent = `${physPct}%`;
    document.getElementById("attr-phys").style.width = `${physPct}%`;
    
    // Prognosis
    const progStressPct = Math.round(data.csm_predictions.stress_index * 100);
    const progLoadPct = Math.round(data.predicted_outcome.predicted_cognitive_load * 100);
    
    const progStressEl = document.getElementById("prog-stress");
    progStressEl.textContent = `${progStressPct}%`;
    document.getElementById("prog-load").textContent = `${progLoadPct}%`;
    
    // Color code prognosis stress
    if (progStressPct < 30) {
        progStressEl.style.color = "var(--color-success)";
    } else if (progStressPct < 60) {
        progStressEl.style.color = "var(--color-amber)";
    } else {
        progStressEl.style.color = "var(--color-danger)";
    }
    
    // Safety lock indicator binding
    const safetyVal = document.getElementById("safety-alert-val");
    if (data.safety.overall_automation_paused) {
        safetyVal.textContent = "Automation Blocked (Manual Override)";
        safetyVal.style.background = "rgba(244, 63, 94, 0.15)";
        safetyVal.style.color = "#fda4af";
    } else {
        safetyVal.textContent = "Automation Allowed";
        safetyVal.style.background = "rgba(16, 185, 129, 0.15)";
        safetyVal.style.color = "#34d399";
    }
    
    // Active System Console Logging
    const logsBody = document.getElementById("console-logs-body");
    data.hardware_logs.forEach(logLine => {
        if (!lastLogs.includes(logLine)) {
            const timeStr = new Date().toLocaleTimeString();
            logsBody.textContent += `\n[${timeStr}] ${logLine}`;
            lastLogs.push(logLine);
        }
    });
    // Keep internal buffer and UI console capped
    if (lastLogs.length > 15) lastLogs.shift();
    const consoleLines = logsBody.textContent.split("\n");
    if (consoleLines.length > 25) {
        logsBody.textContent = consoleLines.slice(consoleLines.length - 25).join("\n");
    }
    logsBody.scrollTop = logsBody.scrollHeight;
    
    // Wearable smartwatch link state indicator (Phase 5)
    const wearableVal = document.getElementById("wearable-status-val");
    if (data.wearable.seconds_since_update !== null && data.wearable.seconds_since_update < 45.0) {
        wearableVal.textContent = `Active Watch (${data.wearable.source})`;
        wearableVal.style.color = "#6ee7b7"; // Light green
    } else {
        wearableVal.textContent = "Simulated Stream";
        wearableVal.style.color = "var(--color-text-sub)";
    }
    
    // Update raw wave charts
    updateChart(data.signals);
}

// Feed signal lists directly to chart datasets
function updateChart(signals) {
    if (!signalsChart) return;
    
    // Replace whole data lines for performance rather than pushing sample by sample
    signalsChart.data.datasets[0].data = signals.eeg;
    signalsChart.data.datasets[1].data = signals.ppg;
    signalsChart.data.datasets[2].data = signals.gsr;
    
    signalsChart.update();
}

// 5. REST trigger endpoints
function setStressor(stress, focus) {
    fetch("/api/stressor", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ stress, focus })
    })
    .then(response => response.json())
    .catch(err => console.error("Stressor POST failed:", err));
}

function overrideActuator(temp, light, noise) {
    fetch("/api/actuator", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ temp, light, noise })
    })
    .then(response => response.json())
    .catch(err => console.error("Actuator POST failed:", err));
}

// YouTube Iframe Player API Handlers
window.onYouTubeIframeAPIReady = function() {
    console.log("[H-SEF Audio] YouTube Player API loaded successfully. Initializing...");
    ytPlayer = new YT.Player('yt-player-element', {
        height: '100%',
        width: '100%',
        videoId: playlistTracks["Focus"][0].id,
        playerVars: {
            'playsinline': 1,
            'controls': 1,
            'disablekb': 1,
            'rel': 0,
            'autoplay': 0
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange
        }
    });
};

// Dynamically load the YouTube IFrame API script to guarantee no race condition
(function() {
    console.log("[H-SEF Audio] Injecting YouTube Player API script dynamically...");
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
})();

function onPlayerReady(event) {
    ytPlayerReady = true;
    document.getElementById("track-name").textContent = playlistTracks["Focus"][0].name;
    ytPlayer.setVolume(50);
}

function onPlayerStateChange(event) {
    const playBtn = document.getElementById("play-btn");
    if (event.data === YT.PlayerState.PLAYING) {
        playBtn.textContent = "⏸ Pause";
        playBtn.className = "btn btn-danger";
    } else {
        playBtn.textContent = "▶ Play";
        playBtn.className = "btn btn-outline";
    }
}

function toggleYTPlay() {
    if (!ytPlayerReady || !ytPlayer) return;
    const state = ytPlayer.getPlayerState();
    if (state === YT.PlayerState.PLAYING) {
        ytPlayer.pauseVideo();
    } else {
        ytPlayer.playVideo();
    }
}

function setYTVolume(vol) {
    if (ytPlayerReady && ytPlayer) {
        ytPlayer.setVolume(vol);
    }
}

function playRandomTrackForCurrentMode() {
    if (!ytPlayerReady || !ytPlayer) return;
    const tracks = playlistTracks[activeYTMode];
    const track = tracks[Math.floor(Math.random() * tracks.length)];
    document.getElementById("track-name").textContent = track.name;
    ytPlayer.loadVideoById(track.id);
}

function syncSensoryMusic(csmState, rlPolicy) {
    if (!ytPlayerReady || !ytPlayer) return;
    
    let targetMode = "Calm";
    if (csmState.stress_index > 0.6) {
        targetMode = "Stress";
    } else if (rlPolicy.target_state === "Focus" || csmState.focus_index > 0.5) {
        targetMode = "Focus";
    }
    
    if (targetMode !== activeYTMode) {
        activeYTMode = targetMode;
        document.getElementById("player-mode-tag").textContent = targetMode;
        
        // Pick a random track in the new category
        const tracks = playlistTracks[targetMode];
        const track = tracks[Math.floor(Math.random() * tracks.length)];
        
        document.getElementById("track-name").textContent = track.name;
        
        // Load and play automatically if already playing, or just cue it
        const playerState = ytPlayer.getPlayerState();
        if (playerState === YT.PlayerState.PLAYING) {
            ytPlayer.loadVideoById(track.id);
        } else {
            ytPlayer.cueVideoById(track.id);
        }
    }
}

function setTargetState(target) {
    fetch("/api/target_state", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ target })
    })
    .then(response => response.json())
    .catch(err => console.error("Target state POST failed:", err));
}

function submitFeedback(rating) {
    fetch("/api/feedback", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ rating })
    })
    .then(response => response.json())
    .then(data => {
        // Subtle console acknowledgement
        const logsBody = document.getElementById("console-logs-body");
        const timeStr = new Date().toLocaleTimeString();
        logsBody.textContent += `\n[${timeStr}] [Feedback Received] Updated RL Epsilon to ${data.epsilon.toFixed(2)}`;
        logsBody.scrollTop = logsBody.scrollHeight;
    })
    .catch(err => console.error("Feedback POST failed:", err));
}

// 7. Location & Live Weather
function setLocation() {
    const city = document.getElementById("location-input").value.trim();
    if (!city) return;

    const btn = document.getElementById("location-btn");
    const errDiv = document.getElementById("location-error");
    const card = document.getElementById("weather-card");

    btn.textContent = "⏳ Fetching…";
    btn.disabled = true;
    errDiv.style.display = "none";

    fetch("/api/location", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city })
    })
    .then(res => res.json())
    .then(data => {
        btn.textContent = "🌍 Set Location";
        btn.disabled = false;

        if (data.status === "error") {
            errDiv.textContent = "⚠ " + data.message;
            errDiv.style.display = "block";
            card.style.display = "none";
            return;
        }

        // Populate the weather card
        const wx = data.weather;
        document.getElementById("weather-location-label").textContent = data.location;
        document.getElementById("wx-condition").textContent  = wx.condition;
        document.getElementById("wx-temp").textContent       = wx.temp + "°C";
        document.getElementById("wx-humidity").textContent   = wx.humidity + "%";
        document.getElementById("wx-wind").textContent       = wx.wind_kph + " km/h";
        card.style.display = "block";

        // Also update the header weather stat immediately
        const weatherEl = document.getElementById("weather-val");
        if (weatherEl) {
            weatherEl.textContent = `${wx.condition}, ${wx.temp}°C · ${data.location}`;
        }

        // Log to console
        const logsBody = document.getElementById("console-logs-body");
        if (logsBody) {
            const t = new Date().toLocaleTimeString();
            logsBody.textContent += `\n[${t}] [Weather] Location set: ${data.location} — ${wx.condition}, ${wx.temp}°C, Humidity ${wx.humidity}%, Wind ${wx.wind_kph} km/h`;
            logsBody.scrollTop = logsBody.scrollHeight;
        }
    })
    .catch(err => {
        btn.textContent = "🌍 Set Location";
        btn.disabled = false;
        errDiv.textContent = "⚠ Network error: " + err.message;
        errDiv.style.display = "block";
    });
}

function saveHardwareConfig() {
    const ip = document.getElementById("config-hue-ip").value;
    const key = document.getElementById("config-hue-key").value;
    
    fetch("/api/config/hardware", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            hue_ip: ip,
            hue_key: key,
            ha_url: "",
            ha_token: ""
        })
    })
    .then(res => res.json())
    .then(data => {
        const logsBody = document.getElementById("console-logs-body");
        const timeStr = new Date().toLocaleTimeString();
        
        let status = "[System] Hardware config updated.";
        if (data.hue_configured) {
            status += " Philips Hue Bridge: CONNECTED.";
        } else {
            status += " Running simulated fallback bridges.";
        }
        
        logsBody.textContent += `\n[${timeStr}] ${status}`;
        logsBody.scrollTop = logsBody.scrollHeight;
        
        if (key) {
            document.getElementById("config-hue-key").value = "";
            document.getElementById("config-hue-key").placeholder = "•••••••••••••••• (Active)";
        }
    })
    .catch(err => console.error("Failed to save hardware config:", err));
}

// 6. Tab Switching Controller
function switchTab(tabId, buttonElement) {
    // Hide all tab contents
    document.querySelectorAll(".tab-content").forEach(el => {
        el.classList.remove("active");
    });
    
    // Deactivate all tab buttons
    document.querySelectorAll(".tab-btn").forEach(el => {
        el.classList.remove("active");
    });
    
    // Show active tab
    const targetTab = document.getElementById(tabId);
    if (targetTab) {
        targetTab.classList.add("active");
    }
    
    // Set button active
    if (buttonElement) {
        buttonElement.classList.add("active");
    }
    
    // Trigger Chart.js resize AFTER the browser has painted the newly visible tab
    // (requestAnimationFrame ensures the element is actually visible with real dimensions)
    if (tabId === 'input-tab' && signalsChart) {
        requestAnimationFrame(() => {
            signalsChart.resize();
            signalsChart.update();
        });
    } else if (tabId === 'output-tab') {
        requestAnimationFrame(() => {
            window.dispatchEvent(new Event('resize'));
        });
    }
}


