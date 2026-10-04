import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

current_dir = os.path.dirname(os.path.abspath(__file__))

ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extractor_args': {'youtube': {'player_client': ['android']}},
    'geo_bypass': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Variable global para recordar el volumen (por defecto 10%)
current_volume = 0.1

# 1. Servidor web falso para cumplir con el requisito de puertos de Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"FlavioMusicc is alive!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()
    
# Iniciar el servidor web en un hilo paralelo
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# 2. Configuración normal del bot con todos los intents activados
bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True, volume=0.5):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable="ffmpeg", options="-vn"), data=data, volume=volume)

@bot.event
async def on_ready():
    print(f"¡Conectado como {bot.user}!")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("¡Pong! El bot está activo.")

@bot.command(name="play")
async def play(ctx, *, search: str):
    """Reproduce audio usando el volumen guardado"""
    if not ctx.author.voice:
        await ctx.send("¡Debes estar en un canal de voz para usar este comando!")
        return

    channel = ctx.author.voice.channel
    if not ctx.voice_client:
        await channel.connect()
    elif ctx.voice_client.is_playing():
        ctx.voice_client.stop()

    async with ctx.typing():
        try:
            query = search if search.startswith("http") else f"ytsearch:{search}"
            
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True, volume=current_volume)
            ctx.voice_client.play(player, after=lambda e: print(f'Error en audio: {e}') if e else None)
            
            await ctx.send(f"🎶 Reproduciendo: **{player.title}** (Volumen: {int(current_volume * 100)}%)")
        except Exception as e:
            await ctx.send(f"Ocurrió un error al reproducir: {e}")

@bot.command(name="stop")
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🛑 Música detenida y bot desconectado del canal de voz.")
    else:
        await ctx.send("¡El bot no está en ningún canal de voz actualmente!")

@bot.command(name="pause")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Música pausada. Usa `!resume` para continuar.")
    else:
        await ctx.send("No hay ninguna música reproduciéndose en este momento.")

@bot.command(name="resume")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Reproducción reanudada.")
    else:
        await ctx.send("El bot no está pausado en este momento.")

@bot.command(name="volume")
async def volume(ctx, vol: int):
    global current_volume

    if vol < 0 or vol > 100:
        await ctx.send("¡El volumen debe ser un número entre 0 y 100!")
        return

    current_volume = vol / 100

    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = current_volume

    await ctx.send(f"🔊 Volumen guardado y ajustado a: **{vol}%**")

@bot.command(name="apagar")
@commands.is_owner()
async def apagar(ctx):
    await ctx.send("🛑 Apagando a FlavioMusicc... ¡Hasta pronto!")
    await bot.close()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)