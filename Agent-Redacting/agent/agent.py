#agent/agent.py
from computers import Computer, LocalPlaywrightComputer
from utils import create_response, show_image
import json
from typing import Callable


class Agent:
    def __init__(
        self,
        model="computer-use-preview",
        computer: Computer = None,
        tools: list[dict] = [],
        acknowledge_safety_check_callback: Callable = lambda: False,
    ):
        self.model = model
        self.computer = computer
        self.tools = tools
        self.print_steps = True
        self.debug = False
        self.show_images = False
        self.acknowledge_safety_check_callback = acknowledge_safety_check_callback

        if computer:
            self.tools += [
                {
                    "type": "computer-use-preview",
                    "display_width": computer.dimensions[0],
                    "display_height": computer.dimensions[1],
                    "environment": computer.environment,
                },
            ]


    def debug_print(self, *args):
        if self.debug:
            print(*args)
    

    def write_log(message):
        LOG_FILE = "debug_log.txt"
        """Helper function to append logs to a file."""
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    # write_log("🚀 Script started...")

    async def handle_item(self, item):
        """Handle each item; may cause a computer action + screenshot."""
        if item["type"] == "message":
            if self.print_steps:
                print(item["content"][0]["text"])
            return []
    
        if item["type"] == "function_call":
            name, args = item["name"], json.loads(item["arguments"])
            if self.print_steps:
                print(f"{name}({args})")
            if hasattr(self.computer, name):
                method = getattr(self.computer, name)
                await method(**args)
                return [
                    {
                        "type": "function_call_output",
                        "call_id": item["call_id"],
                        "output": "success",
                    }
                ]
            # If the function doesn't exist, simply return an empty list.
            return []
    
        if item["type"] == "computer_call":
            action = item["action"]
            action_type = action["type"]
            action_args = {k: v for k, v in action.items() if k != "type"}
            if self.print_steps:
                print(f"{action_type}({action_args})")
    
            await getattr(self.computer, action_type)(**action_args)
    
            # Preserve any specialized handling for specific actions.
            if action_type == "click" and action_args.get("button") == "wheel":
                print("🖱️ Handling wheel click...")
    
            screenshot_base64 = await self.computer.screenshot()
            if self.show_images:
                show_image(screenshot_base64)
    
            # Process pending safety checks.
            # Support both the singular and plural key formats, merging them if needed.
            # ack_checks = []
            # if "pending_safety_check" in item:
            #     pending = item["pending_safety_check"]
            #     if isinstance(pending, dict):
            #         ack_checks.append(pending)
            #     elif isinstance(pending, list):
            #         ack_checks.extend(pending)
            #     else:
            #         print("Unexpected pending_safety_check format:", pending)
    
            pending_checks = item.get("pending_safety_checks")
            # if pending_checks:
            #     if isinstance(pending_checks, dict):
            #         ack_checks.append(pending_checks)
            #     elif isinstance(pending_checks, list):
            #         ack_checks.extend(pending_checks)
    
            for check in ack_checks:
                message = check["message"]
                if not self.acknowledge_safety_check_callback(message):
                    raise ValueError(
                        f"Safety check failed: {message}. Cannot continue with unacknowledged safety checks."
                    )
    
            return [
                {
                    "type": "computer_call_output",
                    "call_id": item["call_id"],
                    "acknowledged_safety_checks": pending_checks,
                    "output": {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{screenshot_base64}",
                    },

                }
            ]
        return []



    async def run_full_turn(self, input_items, print_steps=True, debug=False, show_images=False):
        self.print_steps = print_steps
        self.debug = debug
        self.show_images = show_images
        new_items = []
        while new_items[-1].get("role") != "assistant" if new_items else True:
            self.debug_print(input_items + new_items)
    
            response = create_response(
                model=self.model,
                input=input_items + new_items,
                tools=self.tools,
                truncation="auto",
            )
            self.debug_print(response)
    
            if "output" not in response and self.debug:
                print(response)
                raise ValueError("No output from model")
    
            new_items += response["output"]
            for item in response["output"]:
                new_items += await self.handle_item(item)
    
        return new_items

