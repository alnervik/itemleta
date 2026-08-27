# Tibia Item Matcher

Drar in en extremt pixlad bild på ett Tibia-item och gissar vad det föreställer.

## Kom igång

1. Skapa ett nytt GitHub-repo och lägg in alla filer i den här mappen.
2. Gå till **Settings → Pages** och sätt source till "GitHub Actions".
3. Kör workflowet manuellt en gång: **Actions → Build item database and deploy → Run workflow**.
   Det tar några minuter första gången (laddar ner ~4000+ sprites), men cachas
   sen i `data/signatures.json` som commitas till repot.
4. Sidan blir tillgänglig på `https://<ditt-användarnamn>.github.io/<repo-namn>/`.

## Just nu i `data/signatures.json`

Filen innehåller bara de två exempelbilder du testade i chatten, så du kan
öppna `index.html` lokalt direkt och se att matchningen fungerar innan du
kör hela bygget.

## Vilka items ingår

Databasen byggs bara från TibiaWiki-kategorierna `Body Equipment`, `Weapons`
och `Food` (se `WIKI_CATEGORIES` i `build_signatures.py`), inte alla items i
spelet. Lägg till fler kategorinamn i listan och kör om workflowet för att
utöka urvalet.

## Justera träffsäkerhet

`GRID_SIZE` i `build_signatures.py` styr hur många färgblock varje item
nedskalas till innan jämförelse — måste matcha ungefär den pixelgrad dina
query-bilder har (2×2, 4×4 osv). Ändra och kör om workflowet vid behov.

## Källor & licens

- Itemnamn: [TibiaData API](https://api.tibiadata.com)
- Sprites: [TibiaWiki](https://tibia.fandom.com) (CC-BY-SA, kräver attribution — behåll footern i `index.html`)
- Tibia är ett varumärke tillhörande CipSoft GmbH. Det här är ett ej-officiellt fanverktyg.
