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

// Web Audio API binaural beats variables
let lastLogs = [];
let audioCtx = null;
let leftOsc = null;
let rightOsc = null;
let gainNode = null;
let isAudioPlaying = false;
let currentCarrierFreq = 180;
let currentBinauralOffset = 15;

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
// 3D ROOM VISUALIZATION  (Three.js)
// ============================================================
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
    renderer.toneMappingExposure = 1.1;

    // --- Scene ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f4f8);
    scene.fog = new THREE.Fog(0xf0f4f8, 12, 22);

    // --- Camera ---
    const camera = new THREE.PerspectiveCamera(52, W / H, 0.1, 50);
    camera.position.set(0, 2.8, 6.5);
    camera.lookAt(0, 1.2, 0);

    // --- Materials ---
    const floorMat  = new THREE.MeshStandardMaterial({ color: 0xc8a97e, roughness: 0.8, metalness: 0.0 });
    const wallMat   = new THREE.MeshStandardMaterial({ color: 0xf5f0ea, roughness: 0.95 });
    const ceilMat   = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1.0 });
    const woodMat   = new THREE.MeshStandardMaterial({ color: 0x8b6443, roughness: 0.7 });
    const darkMat   = new THREE.MeshStandardMaterial({ color: 0x2d2d2d, roughness: 0.5 });
    const screenMat = new THREE.MeshStandardMaterial({ color: 0x1a2a4a, emissive: 0x1a2a4a, emissiveIntensity: 0.4, roughness: 0.3 });
    const plantMat  = new THREE.MeshStandardMaterial({ color: 0x3a7d44, roughness: 0.9 });
    const potMat    = new THREE.MeshStandardMaterial({ color: 0xc27b55, roughness: 0.8 });
    const sofaMat   = new THREE.MeshStandardMaterial({ color: 0x7b9eae, roughness: 0.85 });
    const diffMat   = new THREE.MeshStandardMaterial({ color: 0xe8e0f0, roughness: 0.3, metalness: 0.1 });
    const lampShade = new THREE.MeshStandardMaterial({ color: 0xffd89b, emissive: 0xffd89b, emissiveIntensity: 0.6, transparent: true, opacity: 0.85 });

    // --- Room geometry ---
    // Floor
    const floor = new THREE.Mesh(new THREE.BoxGeometry(10, 0.15, 10), floorMat);
    floor.position.set(0, -0.075, 0); floor.receiveShadow = true;
    scene.add(floor);

    // Back wall
    const backWall = new THREE.Mesh(new THREE.BoxGeometry(10, 5, 0.15), wallMat);
    backWall.position.set(0, 2.5, -5); backWall.receiveShadow = true;
    scene.add(backWall);

    // Left wall
    const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.15, 5, 10), wallMat);
    leftWall.position.set(-5, 2.5, 0); leftWall.receiveShadow = true;
    scene.add(leftWall);

    // Right wall
    const rightWall = new THREE.Mesh(new THREE.BoxGeometry(0.15, 5, 10), wallMat);
    rightWall.position.set(5, 2.5, 0); rightWall.receiveShadow = true;
    scene.add(rightWall);

    // Ceiling
    const ceil = new THREE.Mesh(new THREE.BoxGeometry(10, 0.15, 10), ceilMat);
    ceil.position.set(0, 5.075, 0);
    scene.add(ceil);

    // --- Window (back wall, left side) ---
    const windowFrame = new THREE.Mesh(new THREE.BoxGeometry(2.2, 2.2, 0.08), woodMat);
    windowFrame.position.set(-2.2, 2.5, -4.93);
    scene.add(windowFrame);
    const windowGlass = new THREE.Mesh(new THREE.BoxGeometry(1.9, 1.9, 0.04),
        new THREE.MeshStandardMaterial({ color: 0xa8d8f0, transparent: true, opacity: 0.35, roughness: 0.1, metalness: 0.05 }));
    windowGlass.position.set(-2.2, 2.5, -4.93);
    scene.add(windowGlass);

    // Outside glow light from window
    const windowLight = new THREE.RectAreaLight(0x87ceeb, 2.5, 1.8, 1.8);
    windowLight.position.set(-2.2, 2.5, -4.7);
    windowLight.lookAt(-2.2, 2.5, 0);
    scene.add(windowLight);

    // --- Desk ---
    const deskTop = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.1, 1.0), woodMat);
    deskTop.position.set(1.2, 1.2, -3.5); deskTop.castShadow = true; deskTop.receiveShadow = true;
    scene.add(deskTop);
    [-0.3, 1.2].forEach((x, i) => {
        const leg = new THREE.Mesh(new THREE.BoxGeometry(0.08, 1.2, 0.08), woodMat);
        leg.position.set(x + (i === 0 ? -0.85 : 0.85), 0.6, -3.5); leg.castShadow = true;
        scene.add(leg);
    });
    [-3.95, -3.05].forEach(z => {
        const leg2 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 1.2, 0.08), woodMat);
        leg2.position.set(1.2, 0.6, z); leg2.castShadow = true;
        scene.add(leg2);
    });

    // Monitor
    const monBase = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.4, 0.2), darkMat);
    monBase.position.set(1.2, 1.45, -3.8);
    scene.add(monBase);
    const monScreen = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.75, 0.06), screenMat);
    monScreen.position.set(1.2, 1.95, -3.85);
    scene.add(monScreen);

    // Keyboard
    const keyboard = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.04, 0.3), darkMat);
    keyboard.position.set(1.2, 1.27, -3.3);
    scene.add(keyboard);

    // --- Bookshelf (right wall) ---
    const shelfBody = new THREE.Mesh(new THREE.BoxGeometry(0.4, 2.5, 1.6), woodMat);
    shelfBody.position.set(4.8, 1.25, -3.0); shelfBody.castShadow = true;
    scene.add(shelfBody);
    [0.5, 1.0, 1.5, 2.0].forEach(y => {
        const shelf = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.04, 1.5), woodMat);
        shelf.position.set(4.8, y, -3.0);
        scene.add(shelf);
        // Book spines
        const colors = [0xd44, 0x44d, 0x4a4, 0xaa4, 0xd84, 0x94d];
        let bx = -0.55;
        for (let b = 0; b < 5; b++) {
            const book = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.35, 0.2 + Math.random() * 0.1),
                new THREE.MeshStandardMaterial({ color: colors[b % colors.length], roughness: 0.9 }));
            book.position.set(4.8, y + 0.22, bx);
            bx += 0.24;
            scene.add(book);
        }
    });

    // --- Sofa (left back) ---
    const sofaBase = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.45, 0.9), sofaMat);
    sofaBase.position.set(-2.5, 0.35, -3.3); sofaBase.castShadow = true;
    scene.add(sofaBase);
    const sofaBack = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.7, 0.2), sofaMat);
    sofaBack.position.set(-2.5, 0.93, -3.7); sofaBack.castShadow = true;
    scene.add(sofaBack);
    [-1.3, 1.3].forEach(x => {
        const arm = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.55, 0.9), sofaMat);
        arm.position.set(x + (-2.5), 0.5, -3.3);
        scene.add(arm);
    });

    // --- Plant (corner) ---
    const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.14, 0.3, 12), potMat);
    pot.position.set(-4.0, 0.15, -3.8); pot.castShadow = true;
    scene.add(pot);
    const plantBall = new THREE.Mesh(new THREE.SphereGeometry(0.45, 10, 10), plantMat);
    plantBall.position.set(-4.0, 0.75, -3.8); plantBall.castShadow = true;
    scene.add(plantBall);

    // --- Scent Diffuser (on desk) ---
    const diffBase = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.14, 0.28, 12), diffMat);
    diffBase.position.set(2.4, 1.39, -3.5);
    scene.add(diffBase);
    const diffTop  = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.1, 0.12, 10), diffMat);
    diffTop.position.set(2.4, 1.59, -3.5);
    scene.add(diffTop);

    // --- Speaker (desk, left) ---
    const speaker = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.35, 0.18), darkMat);
    speaker.position.set(0.1, 1.43, -3.55);
    scene.add(speaker);

    // --- Ceiling lamp ---
    const lampRod = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.6, 8), darkMat);
    lampRod.position.set(0, 4.8, -1.5);
    scene.add(lampRod);
    const lampCone = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.05, 0.5, 16, 1, true), lampShade);
    lampCone.position.set(0, 4.45, -1.5);
    scene.add(lampCone);

    // --- Lights ---
    // Ambient base
    const ambient = new THREE.AmbientLight(0xfff5e4, 0.35);
    scene.add(ambient);

    // Main ceiling point light (the one that changes with mood)
    const ceilLight = new THREE.PointLight(0xffd89b, 2.5, 12);
    ceilLight.position.set(0, 4.3, -1.5);
    ceilLight.castShadow = true;
    ceilLight.shadow.mapSize.width  = 1024;
    ceilLight.shadow.mapSize.height = 1024;
    scene.add(ceilLight);

    // Subtle fill from desk direction
    const deskFill = new THREE.PointLight(0x8ab4f8, 0.5, 6);
    deskFill.position.set(1.2, 2.2, -3.0);
    scene.add(deskFill);

    // --- Scent particles ---
    const PARTICLE_COUNT = 60;
    const pPositions = new Float32Array(PARTICLE_COUNT * 3);
    const pVels = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
        pPositions[i*3]   = 2.4 + (Math.random()-0.5)*0.08;
        pPositions[i*3+1] = 1.65 + Math.random() * 0.5;
        pPositions[i*3+2] = -3.5 + (Math.random()-0.5)*0.08;
        pVels.push({ vx: (Math.random()-0.5)*0.005, vy: 0.008+Math.random()*0.006, vz: (Math.random()-0.5)*0.004, life: Math.random() });
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
    const pMat = new THREE.PointsMaterial({ color: 0xc4b5fd, size: 0.05, transparent: true, opacity: 0.55, depthWrite: false });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    // --- Sound rings (expand from speaker) ---
    const rings = [];
    for (let r = 0; r < 4; r++) {
        const rGeo = new THREE.RingGeometry(0.01, 0.04, 24);
        const rMat = new THREE.MeshBasicMaterial({ color: 0x60a5fa, transparent: true, opacity: 0.0, side: THREE.DoubleSide });
        const ring = new THREE.Mesh(rGeo, rMat);
        ring.position.set(0.1, 1.6, -3.4);
        ring.rotation.y = Math.PI / 2;
        ring.userData = { phase: r * 0.25, scale: 0.01 };
        scene.add(ring);
        rings.push(ring);
    }

    // --- State targets for smooth lerp ---
    let targetLightColor = new THREE.Color(0xffd89b);
    let targetLightIntensity = 2.5;
    let targetFogDensity = 22;
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

    // --- Animate ---
    function animate() {
        requestAnimationFrame(animate);
        const t = clock.getElapsedTime();

        // Smooth lerp light toward target
        ceilLight.color.lerp(targetLightColor, 0.03);
        ambient.color.lerp(targetLightColor, 0.015);
        lampShade.emissive.lerp(targetLightColor, 0.03);
        ceilLight.intensity += (targetLightIntensity - ceilLight.intensity) * 0.03;

        // Subtle lamp glow bob
        lampCone.material.emissiveIntensity = 0.5 + 0.1 * Math.sin(t * 1.2);

        // Particle animation
        const pos = particles.geometry.attributes.position;
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            pVels[i].life += 0.006;
            pos.array[i*3]   += pVels[i].vx;
            pos.array[i*3+1] += pVels[i].vy * scentIntensity;
            pos.array[i*3+2] += pVels[i].vz;
            if (pVels[i].life > 1.0 || pos.array[i*3+1] > 3.5) {
                pos.array[i*3]   = 2.4 + (Math.random()-0.5)*0.08;
                pos.array[i*3+1] = 1.65;
                pos.array[i*3+2] = -3.5 + (Math.random()-0.5)*0.08;
                pVels[i].life = 0;
                pVels[i].vx = (Math.random()-0.5)*0.005;
                pVels[i].vy = 0.008 + Math.random()*0.006;
            }
        }
        pos.needsUpdate = true;
        pMat.color.lerp(targetParticleColor, 0.05);

        // Sound rings pulse
        rings.forEach((ring, idx) => {
            ring.userData.phase += soundActive ? 0.016 : 0.006;
            const p = ring.userData.phase % 1.0;
            const sc = 0.1 + p * 2.0;
            ring.scale.set(sc, sc, sc);
            ring.material.opacity = soundActive
                ? Math.max(0, 0.55 * (1.0 - p))
                : Math.max(0, 0.15 * (1.0 - p));
        });

        // Slow camera drift for life
        camera.position.x = Math.sin(t * 0.06) * 0.15;
        camera.position.y = 2.8 + Math.sin(t * 0.09) * 0.04;
        camera.lookAt(0, 1.2, 0);

        renderer.render(scene, camera);
    }
    animate();

    // Store reference for live updates
    room3d = {
        ceilLight,
        ambient,
        deskFill,
        windowLight,
        scene,
        pMat,
        particles,
        rings,
        // Public update called from WebSocket handler
        update(rgb, lux, soundOn, scentName, tempC) {
            const r = rgb[0]/255, g = rgb[1]/255, b = rgb[2]/255;
            targetLightColor.setRGB(r, g, b);
            // Brightness from lux: 50lux → 1.0, 400lux → 3.5
            targetLightIntensity = 1.0 + (lux / 400) * 2.5;
            soundActive = soundOn;
            scentIntensity = 0.3 + Math.random() * 0.4;
            // Scent particle color: lavender for calm, citrus-yellow for focus
            if (scentName && scentName.toLowerCase().includes('lemon')) targetParticleColor.set(0xfde68a);
            else if (scentName && scentName.toLowerCase().includes('cedar')) targetParticleColor.set(0xa78f6d);
            else if (scentName && scentName.toLowerCase().includes('pine')) targetParticleColor.set(0x86efac);
            else if (scentName && scentName.toLowerCase().includes('jasmine')) targetParticleColor.set(0xfbcfe8);
            else targetParticleColor.set(0xc4b5fd); // default lavender
            // Window light: cooler when cold outside, warmer inside on cold days
            const wTemp = Math.max(0, Math.min(1, (tempC - 10) / 30));
            windowLight.color.setRGB(0.53 + wTemp * 0.2, 0.81 - wTemp * 0.1, 0.94 - wTemp * 0.3);
            // Monitor screen hint toward light color
            screenMat.emissive.setRGB(r*0.15, g*0.15, b*0.25);
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

    // Phase 3 Synthesizer outputs & dynamic audio tuning
    currentCarrierFreq = data.synthesis.sound.carrier_frequency;
    currentBinauralOffset = data.synthesis.sound.binaural_offset;
    
    if (isAudioPlaying && leftOsc && rightOsc) {
        leftOsc.frequency.setValueAtTime(currentCarrierFreq, audioCtx.currentTime);
        rightOsc.frequency.setValueAtTime(currentCarrierFreq + currentBinauralOffset, audioCtx.currentTime);
    }
    
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

function toggleAudio() {
    const btn = document.getElementById("audio-toggle");
    if (!isAudioPlaying) {
        initAudio();
        btn.textContent = "⏹ Stop Binaural Feed";
        btn.className = "btn btn-danger";
        isAudioPlaying = true;
    } else {
        if (leftOsc) leftOsc.stop();
        if (rightOsc) rightOsc.stop();
        if (audioCtx) audioCtx.close();
        btn.textContent = "🔊 Play Binaural Feed";
        btn.className = "btn btn-outline";
        isAudioPlaying = false;
    }
}

function initAudio() {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    
    // Create oscillators
    leftOsc = audioCtx.createOscillator();
    rightOsc = audioCtx.createOscillator();
    
    leftOsc.type = "sine";
    rightOsc.type = "sine";
    
    leftOsc.frequency.setValueAtTime(currentCarrierFreq, audioCtx.currentTime);
    rightOsc.frequency.setValueAtTime(currentCarrierFreq + currentBinauralOffset, audioCtx.currentTime);
    
    // Create stereo panners
    const leftPanner = audioCtx.createStereoPanner ? audioCtx.createStereoPanner() : null;
    const rightPanner = audioCtx.createStereoPanner ? audioCtx.createStereoPanner() : null;
    
    // Fallback if panners are not supported (mono-ish mixing)
    gainNode = audioCtx.createGain();
    gainNode.gain.setValueAtTime(0.08, audioCtx.currentTime); // Low volume for comfort
    
    if (leftPanner && rightPanner) {
        leftPanner.pan.setValueAtTime(-1, audioCtx.currentTime); // Full Left
        rightPanner.pan.setValueAtTime(1, audioCtx.currentTime);  // Full Right
        
        leftOsc.connect(leftPanner).connect(gainNode);
        rightOsc.connect(rightPanner).connect(gainNode);
    } else {
        leftOsc.connect(gainNode);
        rightOsc.connect(gainNode);
    }
    
    gainNode.connect(audioCtx.destination);
    
    leftOsc.start();
    rightOsc.start();
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


