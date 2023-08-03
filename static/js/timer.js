const FULL_DASH_ARRAY = 283;
const WARNING_THRESHOLD = 600;
const ALERT_THRESHOLD = 300;

const COLOR_CODES = {
  info: {
    color: "green"
  },
  warning: {
    color: "orange",
    threshold: WARNING_THRESHOLD
  },
  alert: {
    color: "red",
    threshold: ALERT_THRESHOLD
  }
};

let TIME_LIMIT = null
let timePassed = null;
let timeLeft = null;
let timerInterval = null;
let remainingPathColor = COLOR_CODES.info.color;

function initTimer(time) {
    TIME_LIMIT = time;
    timePassed = 0;
    timeLeft = time;
    timerInterval = null;
    remainingPathColor = COLOR_CODES.info.color;
    document.getElementById("timer").innerHTML = `
    <div class="base-timer">
      <svg class="base-timer__svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <g class="base-timer__circle">
          <circle class="base-timer__path-elapsed" cx="50" cy="50" r="45"></circle>
          <path
            id="base-timer-path-remaining"
            stroke-dasharray="283"
            class="base-timer__path-remaining ${remainingPathColor}"
            d="
              M 50, 50
              m -45, 0
              a 45,45 0 1,0 90,0
              a 45,45 0 1,0 -90,0
            "
          ></path>
        </g>
      </svg>
      <span id="base-timer-label" class="base-timer__label">${formatTime(
        timeLeft
      )}</span>
    </div>
    `;
}

function onTimesUp() {
  clearInterval(timerInterval);
  document.getElementById('alert').play();
}

function startTimer() {
  tStart = Date.now();
  tEnd = tStart + TIME_LIMIT * 1000;
  timerInterval = setInterval(() => {
    timePassed = timePassed += 1;
    timeLeft = Math.round((tEnd - Date.now())/1000);
    document.getElementById("base-timer-label").innerHTML = formatTime(
      timeLeft
    );
    /*
    document.getElementById("ts").innerHTML = "tStart: " + tStart + "<br>"
						+ "tNow: "+ Date.now() + "<br>"
						+ "tRunning: " + Math.round((Date.now() - tStart) / 1000) + "<br>"
						+ "tLeft: " + Math.round((tEnd - Date.now())/1000) + "<br>"
						+ "tEnd: " + tEnd
						;
    */
    setCircleDasharray();
    setRemainingPathColor(timeLeft);

    if (timeLeft === 0) {
      onTimesUp();
    }
  }, 1000);
}

function stopTimer(time) {
        clearInterval(timerInterval);
        initTimer(time);
}

function formatTime(time) {
    const minutes = Math.floor(time / 60);
    let seconds = time % 60;
    if (seconds < 10) {
        seconds = `0${seconds}`;
    }
    return `${minutes}:${seconds}`;
}

function setRemainingPathColor(timeLeft) {
  const { alert, warning, info } = COLOR_CODES;
  if (timeLeft <= alert.threshold) {
    document
      .getElementById("base-timer-path-remaining")
      .classList.remove(warning.color);
    document
      .getElementById("base-timer-path-remaining")
      .classList.add(alert.color);
  } else if (timeLeft <= warning.threshold) {
    document
      .getElementById("base-timer-path-remaining")
      .classList.remove(info.color);
    document
      .getElementById("base-timer-path-remaining")
      .classList.add(warning.color);
  }
}

function calculateTimeFraction() {
  const rawTimeFraction = timeLeft / TIME_LIMIT;
  return rawTimeFraction - (1 / TIME_LIMIT) * (1 - rawTimeFraction);
}

function setCircleDasharray() {
  const circleDasharray = `${(
    calculateTimeFraction() * FULL_DASH_ARRAY
  ).toFixed(0)} 283`;
  document
    .getElementById("base-timer-path-remaining")
    .setAttribute("stroke-dasharray", circleDasharray);
}
