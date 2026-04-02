# Steam Backlog - What Should I Play?

A fun, interactive web app to help you decide what to play from your Steam backlog.

https://whatshouldiplay.onrender.com/

## Features

- 🎮 **Load Your Backlog** - Connect with your Steam profile to see all your unplayed games
- 🎡 **Spin the Wheel** - Randomly pick a game from your backlog
- ⚔️ **Versus Mode** - Tournament-style game selection
- 🎁 **Mystery Box** - Blind game picking
- 📊 **Smart Filtering** - Filter by playtime, game length (HLTB), genre, and more
- ⏱️ **HowLongToBeat Integration** - See estimated completion times
- 🆓 **Free Games Detection** - Track which games are F2P
- 💾 **Filter Memory** - Your preferences are saved locally

## Local Development

### Prerequisites

- Python 3.8+
- PostgreSQL (or SQLite for local dev)
- Steam API Key (get one at https://steamcommunity.com/dev/apikey)

### Setup

1. Clone the repo and install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file:
```bash
cp .env.example .env
# Edit .env with your STEAM_API_KEY, SECRET_KEY, and DATABASE_URL
```

3. Initialize the database:
```bash
python -c "from database import init_db; init_db()"
```

4. Run the app:
```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

## Performance Tips

- **First sync can be slow** - HLTB has API rate limits. Be patient!
- **Filter before picker** - Only games matching your filters go to the picker
- **Cache your data** - Game data is cached; you can re-sync anytime

## Troubleshooting

### "Profile is private"
Your Steam profile needs to be public to fetch your game library. Check your Steam privacy settings.

### HLTB data missing for some games
Not all games are in the HowLongToBeat database. The app searches by game name and uses fuzzy matching.

### Sync buttons stuck or not updating
Try refreshing the page. Check browser console for errors (F12).

## Share This Project

Know someone with decision paralysis in their Steam library? Share it on:

- **Reddit**: r/Steam, r/gaming, r/webdev
- **Twitter/X**: #Steam #IndieGames #WebDev
- **Discord**: Gaming and development servers

## Technologies Used

- **Backend**: Flask, PostgreSQL, Python
- **Frontend**: Vanilla JavaScript, HTML5 Canvas
- **APIs**: Steam API, HowLongToBeat GraphQL
- **Hosting**: Render.com

## Support

If you find bugs or have feature requests, please open an issue on GitHub.

---

**Built with ❤️ to cure analysis paralysis** 🎮
