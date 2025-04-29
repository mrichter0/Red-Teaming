import time
import base64
import nest_asyncio
import asyncio
import json
import os
from openai import OpenAI
from computers import LocalPlaywrightComputer
from agent.agent import Agent
import re
from pathlib import Path
import cv2
import numpy as np
import pytesseract
nest_asyncio.apply()
conversation_data = []
previous_response_id = None
RESUME = False
RESUME_FILE = "saved_conv/high1.json"  # disabled

def acknowledge_safety_check_callback(message: str) -> bool:
    safe_append_log(f"Auto-acknowledging safety check: {message}")
    return True

def safe_append_log(message):
    global conversation_data
    print(message)
    conversation_data.append(message)


async def capture_and_display(computer, step_name):
    s = await computer.screenshot()
    img_bytes = base64.b64decode(s)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Detect and redact code box
    TARGET_COLOR = np.array([59, 51, 45], dtype=np.uint8)
    TOLERANCE = 2
    lower = TARGET_COLOR - TOLERANCE
    upper = TARGET_COLOR + TOLERANCE
    mask = cv2.inRange(img, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, box_w, box_h = cv2.boundingRect(largest)
        cv2.rectangle(img, (x, y), (x+box_w, y+box_h),
                      (int(TARGET_COLOR[0]), int(TARGET_COLOR[1]), int(TARGET_COLOR[2])), thickness=-1)

    # Redact white regions based on OCR
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    data = pytesseract.image_to_data(img_rgb, output_type=pytesseract.Output.DICT)
    n_boxes = len(data['level'])
    for i in range(n_boxes):
        (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
        if data['text'][i].strip() != "":
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 255, 255), thickness=-1)

    # Draw two horizontal white lines to mask possible leaked text at the bottom area
    h, w, _ = img.shape
    rect_y1 = int(h * 0.75)
    line_thickness = 5
    cv2.line(img, (0, rect_y1), (w, rect_y1), (255, 255, 255), thickness=line_thickness)
    rect_y2 = rect_y1 - line_thickness * 2
    cv2.line(img, (0, rect_y2), (w, rect_y2), (255, 255, 255), thickness=line_thickness)

    retval, buf = cv2.imencode('.png', img)
    redacted_base64 = base64.b64encode(buf).decode('utf-8')
    cv2.imwrite('redacted.png', img)
    return redacted_base64

def get_pending_safety_checks(response):
    output = getattr(response, "output", None) if not isinstance(response, dict) else response.get("output", [])
    if output is None:
        output = []
    pending_checks = []
    for o in output:
        o_type = o["type"] if isinstance(o, dict) else getattr(o, "type", None)
        if o_type == "computer_call":
            for field in ["pending_safety_check", "pending_safety_checks"]:
                pending = o.get(field, None) if isinstance(o, dict) else getattr(o, field, None)
                if pending:
                    if isinstance(pending, list):
                        pending_checks.extend(pending)
                    else:
                        pending_checks.append(pending)
    return pending_checks

async def process_single_action(agent, response, computer):
    l = None
    b = None
    output = getattr(response, "output", None) if not isinstance(response, dict) else response.get("output", [])
    if output is None:
        output = []
    for o in output:
        o_type = o["type"] if isinstance(o, dict) else getattr(o, "type", None)
        if o_type == "message":
            content = o.get("content", [{}]) if isinstance(o, dict) else getattr(o, "content", [])
            if content and len(content) > 0:
                c0 = content[0]
                text = c0["text"] if isinstance(c0, dict) else getattr(c0, "text", "")
            else:
                text = ""
            safe_append_log("🤖 OpenAI says: " + text)
        if o_type == "computer_call":
            l = o.get("call_id") if isinstance(o, dict) else getattr(o, "call_id", None)
            action = o.get("action") if isinstance(o, dict) else getattr(o, "action", {})
            safe_append_log("📩 Processing action: " + str(action))
            act_type = action.get("type") if isinstance(action, dict) else getattr(action, "type", None)
            act_args = {k: v for k, v in (action.items() if isinstance(action, dict) else vars(action).items()) if k != "type"}
            await getattr(computer, act_type)(**act_args)
            b = await capture_and_display(computer, "action_" + str(act_type))
            break
    return l, b

def response_contains_keywords(r, k=None):
    if k is None:
        k = ["would you like", "proceed", "confirm", "are you sure", "should i", "do you"]
    output = getattr(r, "output", None) if not isinstance(r, dict) else r.get("output", [])
    if output is None:
        output = []
    for o in output:
        o_type = o["type"] if isinstance(o, dict) else getattr(o, "type", None)
        if o_type == "message":
            content = o.get("content", [{}]) if isinstance(o, dict) else getattr(o, "content", [])
            if content and len(content) > 0:
                c0 = content[0]
                text = c0["text"] if isinstance(c0, dict) else getattr(c0, "text", "")
            else:
                text = ""
            if any(keyword in text.lower() for keyword in k):
                return True
    return False

if RESUME:
    with open(RESUME_FILE, "r") as f:
        saved = json.load(f)
    previous_response_id = saved["previous_response_id"]
    conversation_data = saved["conversation"]

async def main():
    global previous_response_id
    with open("api_key.txt", "r") as f:
        api_key = f.readline().strip()
    c = OpenAI(api_key=api_key)
    async with LocalPlaywrightComputer() as comp:
        safe_append_log("🚀 Browser initialized. Navigating to DuckDuckGo...")
        # target = "https://www.bing.com/"
        target = "https://feather.openai.com/tasks/db3e371b-deb2-4c64-b0e1-048bd1226527#"
    
        if re.match(r'^https?://', target):
            await comp.goto(target)
        else:
            await comp.goto(Path(target).absolute().as_uri())
        await capture_and_display(comp, "initial_page")
        a = Agent(computer=comp)
        safe_append_log("🤖 Agent is ready. (Type 'exit' or 'save' anytime.)")
        x = False
        while True:
            if x:
                u = "yes"
                safe_append_log("💬 Auto-responding with: yes")
                x = False
                time.sleep(3)
            else:
                u = input("You: ")
                if u.lower() == "exit":
                    safe_append_log("👋 Conversation ended by user.")
                    break
                if u.lower() == "save":
                    safe_append_log("💾 Saving conversation...")
                    if not os.path.exists("saved_conv"):
                        os.makedirs("saved_conv")
                    with open("saved_conv/"+(previous_response_id if previous_response_id else "no_resp_id")+".json", "w") as f:
                        json.dump({"previous_response_id": previous_response_id, "conversation": conversation_data}, f)
                    continue
                conversation_data.append({"role": "user", "content": u})
            for n in range(3):
                try:
                    safe_append_log("Attempt " + str(n+1) + ": Creating response for user input...")
                    r = c.responses.create(
                        model="computer-use-preview",
                        previous_response_id=previous_response_id,
                        truncation="auto",
                        tools=[{"type": "computer_use_preview", "display_width": 1024, "display_height": 768, "environment": "browser"}],
                        input=[{
                            "role": "user",
                            "content": [{
                                "type": "input_text",
                                "text": u
                            }]
                        }]
                    )
                    break
                except Exception as e:
                    safe_append_log("Error during create: " + str(e))
                    if n == 2:
                        raise
                    else:
                        safe_append_log("Retrying...")
            previous_response_id = r.id
            conversation_data.append({"role": "assistant", "content": r.model_dump()})
            safe_append_log("🆔 Agent response ID: " + r.id)
            if response_contains_keywords(r):
                safe_append_log("🔍 Trigger keyword detected. Will auto-respond with 'yes' next round.")
                x = True
            while True:
                l, b = await process_single_action(a, r, comp)
                pending_checks = get_pending_safety_checks(r)
                acknowledged_checks = []
                if pending_checks:
                    safe_append_log("Safety checks received during action processing. Auto-acknowledging...")
                    for check in pending_checks:
                        message = check.get("message", "No message provided") if isinstance(check, dict) else getattr(check, "message", "No message provided")
                        if acknowledge_safety_check_callback(message):
                            acknowledged_checks.append(check)
                    if not acknowledged_checks:
                        safe_append_log("No safety checks acknowledged. Continuing without safety check approval.")
                if not l:
                    break
                for z in range(3):
                    try:
                        input_data = {"call_id": l, "type": "computer_call_output", "output": {"type": "input_image", "image_url": "data:image/png;base64," + b}}
                        if acknowledged_checks:
                            input_data["acknowledged_safety_checks"] = acknowledged_checks
                        r = c.responses.create(
                            model="computer-use-preview",
                            previous_response_id=r.id,
                            truncation="auto",
                            tools=[{"type": "computer_use_preview", "display_width": 1024, "display_height": 768, "environment": "browser"}],
                            input=[input_data]
                        )
                        break
                    except Exception as e:
                        safe_append_log("Error during create: " + str(e))
                        if z == 2:
                            raise
                        else:
                            safe_append_log("Retrying...")
                previous_response_id = r.id
                conversation_data.append({"role": "assistant", "content": r.model_dump()})
                if response_contains_keywords(r):
                    safe_append_log("🔍 Trigger keyword detected in action response. Will auto-respond with 'yes' next round.")
                    x = True

asyncio.run(main())