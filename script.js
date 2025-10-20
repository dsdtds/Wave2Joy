window.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let joystick = null;
    let sessionActive = false;
    let config = {};

    // --- CONSTANTS ---
    const CONSTANT_PULSE_BUZZ_MS = 200;
    const CONSTANT_PULSE_GAP_MS = 100;

    // --- HAPTIC PATTERN GENERATOR (Expanded) ---
    const patternGenerator = {
        // State variables for all modes
        currentTime: 0.0,
        // Stochastic state
        stochasticPhase: 'gap',
        stochasticPhaseEndTime: 0.0,
        stochasticNextMotor: 'left',
        // Constant/Cycle state
        pulseTime: 0.0,
        cyclePhaseIndex: 0,
        lastPulseCycleIndex: -1,
        // Breathing Pulse state
        breathingTime: 0.0,

        start: function() {
            this.currentTime = 0.0;
            this.stochasticPhase = 'gap';
            this.stochasticPhaseEndTime = 0.0;
            this.pulseTime = 0.0;
            this.cyclePhaseIndex = 0;
            this.lastPulseCycleIndex = -1;
            this.breathingTime = 0.0;
        },

        // --- MODE-SPECIFIC UPDATE FUNCTIONS ---

        updateStochastic: function(dt) {
            this.currentTime += dt;
            if (this.currentTime >= this.stochasticPhaseEndTime) {
                if (this.stochasticPhase === 'gap') {
                    this.stochasticPhase = 'buzz';
                    const buzzDuration = Math.random() * (config.buzzMax - config.buzzMin) + config.buzzMin;
                    this.stochasticPhaseEndTime = this.currentTime + buzzDuration / 1000.0;
                    this.stochasticNextMotor = Math.random() < 0.5 ? 'left' : 'right';
                } else {
                    this.stochasticPhase = 'gap';
                    const gapDuration = Math.random() * config.maxGap;
                    this.stochasticPhaseEndTime = this.currentTime + gapDuration / 1000.0;
                }
            }
            let left = 0.0, right = 0.0;
            if (this.stochasticPhase === 'buzz') {
                const progress = Math.min(1.0, this.currentTime / config.peakTime);
                const easedProgress = progress * progress;
                const globalMultiplier = 0.3 + 0.7 * easedProgress;
                const baseIntensity = Math.random() * (config.strongIntensity - config.weakIntensity) + config.weakIntensity;
                const targetIntensity = baseIntensity * globalMultiplier;
                if (this.stochasticNextMotor === 'left') left = targetIntensity;
                else right = targetIntensity;
            }
            return { left, right };
        },

        updateBreathingPulse: function(dt) {
            this.breathingTime += dt;
            const basePeriod = config.breathingPulsePeriod;
            const syncPeriod = config.breathingPulseSyncPeriod;
            const baseFreq = 1.0 / (basePeriod > 0 ? basePeriod : 1);
            const beatFreq = 1.0 / (syncPeriod > 0 ? syncPeriod : 1);
            const freqLeft = baseFreq;
            const freqRight = baseFreq + beatFreq;
            const center = (config.maxIntensity + config.breathingPulseMinIntensity) / 2.0;
            const amplitude = (config.maxIntensity - config.breathingPulseMinIntensity) / 2.0;
            const phaseLeft = 2 * Math.PI * freqLeft * this.breathingTime;
            const intensityLeft = center + amplitude * Math.sin(phaseLeft);
            const phaseRight = 2 * Math.PI * freqRight * this.breathingTime;
            const intensityRight = center + amplitude * Math.sin(phaseRight);
            return { left: intensityLeft, right: intensityRight };
        },

        updateConstant: function(dt, mode) {
            this.pulseTime += dt * 1000;
            const totalPulseDuration = CONSTANT_PULSE_BUZZ_MS + CONSTANT_PULSE_GAP_MS;
            const phaseTime = this.pulseTime % totalPulseDuration;
            let left = 0.0, right = 0.0;
            if (phaseTime < CONSTANT_PULSE_BUZZ_MS) {
                let intensity = 0.0;
                if (mode === 'constant_weak') intensity = config.weakIntensity;
                else if (mode === 'constant_strong') intensity = config.strongIntensity;
                else if (mode === 'constant_max') intensity = config.maxIntensity;
                left = right = intensity;
            }
            return { left, right };
        },

        updateCycle: function(dt) {
            this.pulseTime += dt * 1000;
            const totalPulseDuration = CONSTANT_PULSE_BUZZ_MS + CONSTANT_PULSE_GAP_MS;
            const currentPulseCycleIndex = Math.floor(this.pulseTime / totalPulseDuration);
            if (currentPulseCycleIndex > this.lastPulseCycleIndex) {
                this.cyclePhaseIndex = (this.cyclePhaseIndex + 1) % 4;
                this.lastPulseCycleIndex = currentPulseCycleIndex;
            }
            const phaseTime = this.pulseTime % totalPulseDuration;
            let left = 0.0, right = 0.0;
            if (phaseTime < CONSTANT_PULSE_BUZZ_MS) {
                let intensity = 0.0;
                switch (this.cyclePhaseIndex) {
                    case 0: // Phase 1: Strong, both
                        intensity = config.strongIntensity;
                        left = right = intensity;
                        break;
                    case 1: // Phase 2: Max, both
                        intensity = config.maxIntensity;
                        left = right = intensity;
                        break;
                    case 2: // Phase 3: Max, left
                        intensity = config.maxIntensity;
                        left = intensity;
                        break;
                    case 3: // Phase 4: Max, right
                        intensity = config.maxIntensity;
                        right = intensity;
                        break;
                }
            }
            return { left, right };
        }
    };

    // --- UI ELEMENT REFERENCES ---
    const ui = {
        status: document.getElementById('status'),
        startButton: document.getElementById('startButton'),
        stopButton: document.getElementById('stopButton'),
        timer: document.getElementById('timer'),
        leftMotorBar: document.getElementById('leftMotorBar'),
        leftMotorValue: document.getElementById('leftMotorValue'),
        rightMotorBar: document.getElementById('rightMotorBar'),
        rightMotorValue: document.getElementById('rightMotorValue'),
        phaseInfo: document.getElementById('phaseInfo'),
        intensityInfo: document.getElementById('intensityInfo'),
        liveInfoBox: document.getElementById('liveInfoBox'),
        modeSelect: document.getElementById('modeSelect'),
        stochasticSettings: document.getElementById('stochasticSettings'),
        breathingPulseSettings: document.getElementById('breathingPulseSettings'),
    };

    // --- SLIDER SETUP ---
    const sliders = {
        sessionLength: document.getElementById('sessionLength'),
        peakTime: document.getElementById('peakTime'),
        weakIntensity: document.getElementById('weakIntensity'),
        strongIntensity: document.getElementById('strongIntensity'),
        maxIntensity: document.getElementById('maxIntensity'),
        buzzMin: document.getElementById('buzzMin'),
        buzzMax: document.getElementById('buzzMax'),
        maxGap: document.getElementById('maxGap'),
        breathingPulseMinIntensity: document.getElementById('breathingPulseMinIntensity'),
        breathingPulsePeriod: document.getElementById('breathingPulsePeriod'),
        breathingPulseSyncPeriod: document.getElementById('breathingPulseSyncPeriod'),
    };

    function updateConfigFromUI() {
        config.mode = ui.modeSelect.value;
        for (const key in sliders) {
            if (sliders[key]) {
                config[key] = parseFloat(sliders[key].value);
                const valueSpan = document.getElementById(`${key}Value`);
                if (valueSpan) {
                    let suffix = '';
                    if (key.includes('Time') || key.includes('Gap') || key.includes('Buzz')) suffix = 'ms';
                    if (key.includes('session') || key.includes('peak') || key.includes('Period')) suffix = 's';
                    valueSpan.textContent = sliders[key].value + suffix;
                }
            }
        }
    }

    Object.values(sliders).forEach(slider => slider.addEventListener('input', updateConfigFromUI));
    ui.modeSelect.addEventListener('change', () => {
        updateConfigFromUI();
        handleModeChange();
    });

    // --- UI LOGIC ---
    function handleModeChange() {
        const mode = ui.modeSelect.value;
        ui.stochasticSettings.classList.toggle('hidden', mode !== 'stochastic');
        ui.breathingPulseSettings.classList.toggle('hidden', mode !== 'breathing_pulse');
        ui.liveInfoBox.classList.toggle('hidden', mode !== 'stochastic');

        // Set sensible defaults for session length when switching modes
        if (mode.startsWith('constant') || mode === 'cycle' || mode === 'breathing_pulse') {
            sliders.sessionLength.value = 3600;
        } else {
            sliders.sessionLength.value = 300;
        }
        updateConfigFromUI();
    }

    // --- GAMEPAD API ---
    function handleGamepadConnect(event) {
        joystick = event.gamepad;
        ui.status.textContent = `Controller Connected: ${joystick.id}`;
        ui.status.style.color = 'var(--active-color)';
    }
    function handleGamepadDisconnect() {
        joystick = null;
        ui.status.textContent = "Controller Disconnected.";
        ui.status.style.color = 'var(--text-color)';
        if (sessionActive) stopSession();
    }
    window.addEventListener("gamepadconnected", handleGamepadConnect);
    window.addEventListener("gamepaddisconnected", handleGamepadDisconnect);

    // --- SESSION MANAGEMENT ---
    let sessionStartTime = 0;
    let lastUpdateTime = 0;

    function startSession() {
        if (!joystick || !joystick.connected) {
            alert("Controller not detected.");
            return;
        }
        if (!joystick.vibrationActuator) {
            alert("This controller does not support vibration.");
            return;
        }
        sessionActive = true;
        ui.startButton.disabled = true;
        ui.stopButton.disabled = false;
        updateConfigFromUI();
        patternGenerator.start();
        sessionStartTime = Date.now();
        lastUpdateTime = sessionStartTime;
        requestAnimationFrame(gameLoop);
    }

    function stopSession() {
        sessionActive = false;
        ui.startButton.disabled = false;
        ui.stopButton.disabled = true;
        if (joystick && joystick.connected && joystick.vibrationActuator) {
            joystick.vibrationActuator.playEffect("dual-rumble", {
                duration: 50, weakMagnitude: 0.0, strongMagnitude: 0.0
            });
        }
        updateVisualizer(0, 0);
        ui.phaseInfo.textContent = 'IDLE';
    }

    ui.startButton.addEventListener('click', startSession);
    ui.stopButton.addEventListener('click', stopSession);

    // --- MAIN LOOP ---
    function gameLoop() {
        if (!sessionActive) return;
        const now = Date.now();
        const dt = (now - lastUpdateTime) / 1000.0;
        lastUpdateTime = now;
        const elapsed = (now - sessionStartTime) / 1000.0;
        if (elapsed >= config.sessionLength) {
            stopSession();
            return;
        }

        let motorValues = { left: 0, right: 0 };
        switch (config.mode) {
            case 'stochastic':
                motorValues = patternGenerator.updateStochastic(dt);
                break;
            case 'breathing_pulse':
                motorValues = patternGenerator.updateBreathingPulse(dt);
                break;
            case 'cycle':
                motorValues = patternGenerator.updateCycle(dt);
                break;
            case 'constant_weak':
            case 'constant_strong':
            case 'constant_max':
                motorValues = patternGenerator.updateConstant(dt, config.mode);
                break;
        }
        
        // Clamp values to be safe
        motorValues.left = Math.max(0, Math.min(255, motorValues.left));
        motorValues.right = Math.max(0, Math.min(255, motorValues.right));

        if (joystick && joystick.connected && joystick.vibrationActuator) {
            joystick.vibrationActuator.playEffect("dual-rumble", {
                duration: 200,
                weakMagnitude: motorValues.right / 255.0,
                strongMagnitude: motorValues.left / 255.0,
            });
        }
        updateVisualizer(motorValues.left, motorValues.right, elapsed);
        requestAnimationFrame(gameLoop);
    }

    function updateVisualizer(left, right, elapsed = 0) {
        ui.leftMotorBar.style.width = `${(left / 255) * 100}%`;
        ui.leftMotorValue.textContent = Math.round(left);
        ui.rightMotorBar.style.width = `${(right / 255) * 100}%`;
        ui.rightMotorValue.textContent = Math.round(right);
        ui.timer.textContent = `Time: ${Math.floor(elapsed)}s / ${config.sessionLength}s`;
        if (config.mode === 'stochastic') {
            const progress = Math.min(1.0, patternGenerator.currentTime / config.peakTime);
            const globalMultiplier = 0.3 + 0.7 * (progress * progress);
            ui.phaseInfo.textContent = patternGenerator.stochasticPhase.toUpperCase();
            ui.intensityInfo.textContent = `${Math.round(globalMultiplier * 100)}%`;
        }
    }

    // --- INITIALIZE ---
    handleModeChange();
    updateConfigFromUI();
});