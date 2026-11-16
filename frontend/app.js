const logE1 = document.getElementById("log");
const log = (text) => { logE1.textContent += text + "\n"; };

const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onopen = () => log("connected to server");
ws.onmessage = (event) => log(`<- ${event.data}`);
ws.onclose = () => log('disconnected');

document.getElementById("send").onclick = () => {
    const msg = `hello at ${new Date().toLocaleTimeString()}`;
    ws.send(msg);
    log(`-> ${msg}`);
};
