# Veikart og løsningsskisse: UniMicro V3 → produktgraf

**Status:** Forslag til vurdering, ikke implementert integrasjon  
**Sist vurdert:** 14. oktober 2026  
**Tilhørende tegning:** [Arkitektur og dataflyt](architecture-data-flow.svg)  
**Utforskbar graf i appen:** `?graph=application-architecture`

## Mål og beslutning

La UniMicro V3 være fasit for avtalte varedata, og oppdater Autic-grafen automatisk uten at nettleser eller offentlig webserver får tilgang til CRM-databasen. Første versjon bruker planlagt, periodisk lesing fra Microsoft SQL Server. Den publiserer bare en godkjent, lesbar kopi av grafen.

**Anbefalt beslutning:** Start med en intern eksportjobb og statisk publisering. Kartlegg først hvordan dagens nettsted leser og filtrerer V3-varer; gjenbruk gjerne en dokumentert, avgrenset eksport fra den løsningen dersom den har alle nødvendige felt. Direkte SQL-lesing er alternativet når eksporten ikke dekker behovet. Ingen kobling mellom den offentlige appen og SQL-serveren er nødvendig.

Dette dokumentet er en arkitekturskisse. Det inneholder ikke faktiske tabellnavn, legitimasjon, nettverksadresser eller påstander om intern varemodell; de må avklares i deres miljø.

## Det som finnes i prosjektet nå

| Del | Dagens rolle |
| --- | --- |
| `graphs/autic-products.json` | Manuelt kuratert eksempel; 44 noder og 80 relasjoner. Inneholder produkter, produsenter, kategorier, protokoller, bruksområder og bransjer. |
| `graph_starters/autic-products.json` | Tilbakestillingsgrunnlag for samme graf. |
| `app.py` og `graph_store.py` | Flask-endepunkter som leser, redigerer, validerer og lagrer JSON-grafer. `graph_store.py` skriver via midlertidig fil og atomisk erstatning. |
| `templates/index.html` og `static/app.js` | Nettleservisning med Cytoscape. Biblioteket lastes fra CDN. |
| `classifier.py` | Lokale plasseringsforslag; kan også sende grafinnhold til OpenAI hvis `OPENAI_API_KEY` er satt. |
| `scripts/build_demo.py` og `demo/` | Lager en statisk, lesbar Autic-demo fra gjeldende JSON. |
| `.github/workflows/pages.yml` | Bygger og publiserer den statiske demoen ved push til `main`. |

Flask-appen har redigerings- og reset-endepunkter og er ikke en produksjonsklar offentlig publiseringsflate. Den statiske demoen eksponerer hele `demo/graph.json` for dem som kan nå siden. Verken den eksisterende JSON-filen eller Git-repositoriet skal derfor bli en ufiltrert kopi av CRM-data.

## Foreslått dataflyt

```text
Intern sone                                      Publiseringssone
UniMicro V3 / klientbase i MSSQL
  → dedikert SQL-identitet med snever SELECT
  → planlagt synkroniseringsjobb
  → uttrekk → normalisering → godkjent feltliste
  → sammenstilling med kuraterte relasjoner
  → validering og kontroll av avvik
  → ferdig, versjonert JSON-artefakt
  → kontrollert utgående publisering            → statisk graf → nettleser
```

Den eksisterende nettsidens kobling til V3 er en **kjent opplysning fra virksomheten, men ikke undersøkt i dette prosjektet**. Kartleggingen må vise hvor koblingen kjører, hvilke data den allerede eksporterer, hvordan «vis på web» avgjøres, og om et avgrenset produktuttrekk kan gjenbrukes. Vi bør unngå å opprette en ekstra SQL-tilgang dersom samme godkjente data kan hentes fra en trygg intern eksport.

Plasser synkroniseringskoden i en egen modul og kjør den med operativsystemets oppgaveplanlegger eller tilsvarende driftsplattform. Ikke la `app.py`, en HTTP-forespørsel eller hver enkelt nettleserøkt starte SQL-lesing. Som startpunkt kan jobben gå hvert 15. minutt; faktisk intervall bestemmes av datavolum, belastning og hvor raskt nye varer må vises. Ved feil beholdes siste godkjente artefakt, og drift varsles. Ingen halvskrevet eller tom graf publiseres.

### Dataeierskap og mapping

| Felt/relasjon i grafen | Foreslått kilde | Regel som må avklares |
| --- | --- | --- |
| Produkt-ID | Stabil intern produktnøkkel eller varenummer fra V3 | Stabil ved navneendring; håndter gjenbruk av varenummer. |
| Produktnavn, offentlig beskrivelse | Godkjente varefelt/eksport | Vask og lengdebegrens tekst; ikke ta med interne notater. |
| Aktiv/publiserbar status | V3 og/eller dagens nettsted | Definer hvilke varer som kan publiseres. |
| Offentlig produkt-URL | Dagens nettsted eller godkjent mapping | Tillat bare forventet HTTPS-domene; ikke konstruer URL blindt fra varenummer. |
| Produsent og varegruppe | V3 dersom feltene er pålitelige; ellers kuratert mapping | Avklar duplikater, alias og hierarki. |
| Protokoll, teknologi, bruksområde, bransje | Egen kuratert kunnskapsbase eller eksplisitte, kvalitetssikrede varefelt | Ikke utled tekniske påstander fra navn alene. |
| Pris, rabatt, kunde, ordre og CRM-notater | Ingen | Skal ikke leses for denne jobben eller publiseres. |

Start med én tydelig regel for hvilke produkter som skal med. UniMicro V3 er fasit for varedata; de kuraterte relasjonene er et separat datasett med egen eier. Eksisterende noder bør kobles til V3-nøkler før automatisk generering tas i bruk. Bruk helst et eksplisitt `source_system`/`source_id`-grunnlag i generatoren; grafens synlige ID kan da avledes stabilt. Ikke bruk produktnavn som ID.

### Synkroniseringsregler

1. Hent et konsistent, avgrenset uttrekk. Første versjon kan lese hele settet av publiserbare produkter på hvert intervall dersom volum og belastning tillater det. Bruk tidsgrenser og mål varighet.
2. Normaliser og kontroller ID-er, obligatoriske felt, tekstlengde, URL-er og antall. Lag kun eksplisitt tillatte felt i den offentlige grafen.
3. Slå sammen vareuttrekket med den kuraterte grafmodellen. Bevar håndlagde relasjoner som fortsatt peker på gyldige noder. Rapporter relasjoner som mister endepunkt.
4. Nye varer får nye noder. Endringer i kildedata oppdaterer bare kildeeide felt. En vare som ikke lenger er publiserbar fjernes fra offentlig visning etter definert regel; sletting i V3, midlertidig feil i uttrekk og deaktivert vare må skilles.
5. Valider hele resultatet med `graph_store.validate_graph`, forventet nodeantall og avviksgrenser. Ved uventet stort bortfall kreves manuell gjennomgang før publisering.
6. Publiser atomisk med versjon/tidspunkt og bevar siste godkjente versjon for rask tilbakeføring. En jobb må være idempotent: samme kildeuttrekk skal gi samme graf.

SQL Server Change Tracking kan vurderes senere ved stort datavolum eller krav om kort forsinkelse. Det er **ikke** del av første fase: funksjonen må aktiveres på database og tabeller og medfører driftsendring. En vanlig planlagt jobb er enklere å revidere og feilsøke.

## Sikkerhetskrav før produksjon

1. **Nettverk:** Jobben kjøres internt. Bare jobbens vert får nå relevant SQL-endepunkt. Ingen inngående forbindelse fra internett, GitHub Actions eller offentlig webserver til CRM/SQL. Publisering skjer utgående fra intern sone til en avgrenset destinasjon.
2. **SQL-rettigheter:** Egen tjenesteidentitet med kun nødvendig `SELECT`, helst på en dedikert visning eller få objekter. Ingen `db_datareader` for hele klientbasen, `db_owner`, `sysadmin`, skrivetilgang, generell prosedyrekjøring eller gjenbruk av nettstedets/administratorens konto. Gjennomgå rettighetene i faktisk V3-oppsett med databaseansvarlig.
3. **Hemmeligheter:** Lagres i driftsplattformens hemmelighetslager eller tilsvarende, aldri i kode, JSON, Git, logg, byggartefakt eller klientkode. Roterbare legitimasjoner og kryptert transport til SQL-serveren.
4. **Dataminimering:** Eksplisitt allowlist for felter og produkter. En lokal kontroll må vise nøyaktig publisert JSON før produksjonssetting. Avklar om enkelte produkter, navn eller lenker er konfidensielle.
5. **Publisering:** Den statiske JSON-filen behandles som offentlig. Ikke legg genererte interne data i `graphs/`, `graph_starters/`, `demo/` eller et offentlig Git-repositorium uten godkjenning. Dagens GitHub Pages-arbeidsflyt bygger fra Git; produksjonsflyten må velges bevisst.
6. **App-tilgang:** Dersom Flask-appen brukes utenfor utviklingsmiljø, krev autentisering, autorisasjon, CSRF-beskyttelse og eget oppsett for produksjon før redigeringsendepunktene eksponeres. Alternativet for offentlig visning er den statiske, lesbare demoen.
7. **Eksterne tjenester:** `classifier.py` kan sende grafnoder og relasjoner til OpenAI ved bruk av `OPENAI_API_KEY`. Denne funksjonen må holdes av for interne/ikke-godkjente data inntil databehandlingen er vurdert.
8. **Drift:** Logg antall hentede, opprettede, oppdaterte, deaktiverte og avviste produkter, kjørevarighet og publisert versjon. Logg aldri hemmeligheter eller rå CRM-rader. Varsle ved feil, uteblitt kjøring eller store avvik. Bevar siste gode versjon og dokumenter tilbakeføring.

Lesetilgang alene er ikke en full sikkerhetsgrense: kompromitteres en prosess med bred `SELECT`, kan den likevel hente konfidensielle data. Derfor må SQL-rettighet, nettverk og feltfiltrering alle være snevre.

## Veikart og leveranser

| Fase | Arbeid | Ferdig når |
| --- | --- | --- |
| 0. Kartlegging | IT/produkteier viser eksisterende nettsideflyt, V3-klientbase, aktuelle varefelt, publiseringsflagg, volum og driftsmiljø. | Feltmapping, godkjent produktutvalg og valgt tilgangsvei er dokumentert. Ingen legitimasjon deles i repoet. |
| 1. Lokal prototype | Lag uttrekk mot maskerte/testdata, transformasjon til samme grafskjema, stabil ID-mapping og sammenstilling med kuraterte relasjoner. | Flere kjøringer gir deterministisk resultat; nye/endrede/utgåtte varer håndteres i testdata. |
| 2. Intern pilot | Opprett snever SQL-identitet, intern planlagt jobb, kontrollert artefakt og logg/varsling. | IT verifiserer faktisk SQL-tilgang og at verken webserver eller nettleser kan nå SQL. Avvik stopper publisering. |
| 3. Publisering | Bestem intern/ekstern målgruppe, gjennomgå offentlig JSON, sett opp publiseringskanal og tilbakeføring. | Produkteier godkjenner synlige felt og utvalg; siste gode versjon kan gjenopprettes. |
| 4. Drift | Mål belastning, oppdateringsforsinkelse og vedlikehold av kuraterte koblinger. | Eier, rutiner og alarmmottak er avklart; intervall justeres etter faktisk behov. |

### Åpne spørsmål som avgjør designet

- Hvilket system og hvilken kode bestemmer i dag hvilke V3-varer nettstedet viser? Finnes allerede et avgrenset produktuttrekk som kan gjenbrukes?
- Hvilken V3-klientbase og hvilke konkrete tabeller/visninger/felt er relevante? Finnes endringsstempel, publiseringsflagg og stabil produktnøkkel?
- Hvilke varer er offentlige, og hvilke felt kan faktisk eksponeres? Skal grafen være offentlig eller kun intern?
- Hvordan behandles utgåtte produkter, midlertidig manglende data og manuelt kuraterte relasjoner?
- Hvor mange produkter skal vises? Ved større katalog kan kategoribasert utsnitt/søk være mer lesbart enn én stor graf.
- Hvor skal den interne jobben kjøre, og hvilken godkjent kanal kan levere JSON til visningsmiljøet?

## Referanser og avgrensning

- [UniMicro: innholdet i V3-klientbasen](https://support.unimicro.no/kundestotte/teknisk/backup/backup-fil-inneholder) beskriver varer i klientbasen.
- [UniMicro: konfigurering av SQL Server](https://support.unimicro.no/kundestotte/teknisk/installasjon-og-nettverk/mssql/konfigurering-av-sql-server) bekrefter MSSQL som V3-datamotor.
- [UniMicro Platform: getting started](https://developer.unimicro.no/guide/intro/getting-started) beskriver plattformens API, men dokumenterer ikke at det gir tilgang til en lokal V3-installasjon.
- [Microsoft: least privilege for SQL Server](https://learn.microsoft.com/en-us/sql/relational-databases/security/authentication-access/getting-started-with-database-engine-permissions?view=sql-server-ver17) underbygger snever `SELECT`.
- [Microsoft: Change Tracking](https://learn.microsoft.com/en-us/sql/relational-databases/track-changes/about-change-tracking-sql-server?view=sql-server-ver17) beskriver hva senere inkrementell synkronisering ville kreve.
