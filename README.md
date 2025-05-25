# Token Racer 🏎️

A retro ASCII racing game for the terminal, powered by OpenAI-compatible LLM for track generation.
After gear 1 runs only on Cerebras.

## Why This Game Is Wildly Inefficient

Token Racer doesn’t just use an LLM to sprinkle in flavor. Instead, it **abuses** a large language model to generate every single new stretch of road as you drive—live, line by line, in real time. The player’s progress is entirely dependent on remote inference calls, making this game the least scalable and most computationally ~~stupid~~ extravagant use of AI for a racing game in history. (It’s also weirdly fun.)

**In short:**  
Instead of your CPU procedurally generating the world,  
**LLM is generating every meter of road beneath your wheels, live.**  
The car isn’t driving on code—it’s driving on inference!

- This is the “Stochastic Parallax Highway” of AI games.
- Please do not use this to benchmark your cloud bill or AI quota!
- Try the fallback offline mode if you want to be kind to your compute budget.

**Enjoy the absurdity**


## Features

- Smooth, animated racing in your terminal
- Free car movement with WASD or arrow keys (WOW)
- Variable gears and speed for arcade feel
- Centered, LLM generated road with obstacles
- Incredible waste of compute


## Controls

- `W`, `A`, `S`, `D` or Arrow Keys — Move car
- `SPACE` — Shift gear up (no way back)
- `Q` or `Ctrl+C` — Quit

## Getting Started
Just python token_racer.py in your console.
