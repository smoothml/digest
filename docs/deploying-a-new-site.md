# Deploying a new site

This guide takes a new site in `sites/<name>/` from an empty folder to a live website with a verified [standard.site](https://standard.site) publication on the AT Protocol. It reflects how `hansard` (orderly.bot) was set up.

A site consists of:

| Part | Where it lives |
|---|---|
| Hugo site | `sites/<name>/` |
| Domain and web host | outside the repo, reached by rsync over SSH |
| AT Protocol identity | `sites/<name>/static/.well-known/did.json` and `atproto-did` |
| PDS account | on `eurosky.social`, created once by hand |
| Sequoia config | `sites/<name>/sequoia.json` |
| Task wiring | `Taskfile.yml` and `.env` |

Generating content for a new source is separate work in `src/digest` and `scripts/summarise_<name>.sh`. This guide covers only the site and its publishing.

## Prerequisites

- `hugo`, `task`, `rsync`, and an SSH key for the web host.
- Node 20 or newer and the Sequoia CLI: `npm i -g sequoia-cli`. With asdf, run `asdf reshim nodejs` afterwards, and reinstall if you change Node version.
- `goat`, the AT Protocol CLI: `go install github.com/bluesky-social/goat@latest`.
- A domain with hosting that serves files under `/.well-known/`, including extensionless ones, and serves `did.json` as JSON.
- An email address not already used on an Eurosky account.

## 1. Create the Hugo site

Create `sites/<name>/` with `hugo.toml`, `layouts/`, `content/`, and `static/.well-known/`. Set `baseURL` to the site's domain.

Keep Hugo's default URL scheme, so a post at `content/<section>/<file>.md` is served at `/<section>/<file>/`. Sequoia derives each record's URL from the file path in the same way, and the two must agree. Use lowercase, hyphenated filenames.

## 2. Register the site with Task

In `Taskfile.yml`, add `<name>` to the `enum` under `__validate_site`, and add an entry for it to each of the three maps:

```yaml
SITE_TO_IDENTITY:
  map:
    hansard: '{{ env "SITE_IDENTITY_HANSARD" | default (env "SITE_IDENTITY") }}'
    <name>: '{{ env "SITE_IDENTITY_<NAME>" | default (env "SITE_IDENTITY") }}'
```

Do the same for `SITE_TO_USER` and `SITE_TO_HOST`. Then add to `.env`:

```
SITE_HOST_<NAME>=<host>
SITE_USER_<NAME>=<ssh user>
SITE_IDENTITY_<NAME>=<path to ssh key>
```

`.env` is gitignored.

## 3. Deploy the plain site

The AT Protocol steps below need the site live first, so deploy it now without Sequoia:

```bash
task build SITE=<name>
task deploy-site SITE=<name>
```

`deploy-site` only uploads `public/`, so always build before it. Check the site in a browser.

## 4. Create the identity

The site's domain becomes its AT Protocol identity, `did:web:<domain>`. Whoever can write to the web root controls the identity, and the identity lasts only as long as the domain and hosting do. There is no way to change a `did:web` identity into a `did:plc` one later.

Generate a temporary key. Keep the secret in a password manager:

```bash
goat key generate --type K-256
```

Write `sites/<name>/static/.well-known/did.json`, with the public key minus its `did:key:` prefix:

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/multikey/v1",
    "https://w3id.org/security/suites/secp256k1-2019/v1"
  ],
  "id": "did:web:<domain>",
  "alsoKnownAs": ["at://<domain>"],
  "verificationMethod": [
    {
      "id": "did:web:<domain>#atproto",
      "type": "Multikey",
      "controller": "did:web:<domain>",
      "publicKeyMultibase": "<public key, starts zQ3sh>"
    }
  ],
  "service": [
    {
      "id": "#atproto_pds",
      "type": "AtprotoPersonalDataServer",
      "serviceEndpoint": "https://eurosky.social"
    }
  ]
}
```

Write `sites/<name>/static/.well-known/atproto-did` containing only:

```
did:web:<domain>
```

Build and deploy the site again, then check both files resolve:

```bash
goat resolve did:web:<domain>
goat resolve <domain>
```

The endpoint must be `https://eurosky.social` exactly. The PDS compares it as a string.

## 5. Create the PDS account

Eurosky gates sign-up behind a captcha, and its sign-up form does not accept a handle with a dot in it. So the account is created with a raw request that carries three things: proof you control the DID, a captcha code, and the `did` field.

Sign the proof. Give it an hour so it outlives the captcha code:

```bash
goat account service-auth-offline \
  --atproto-signing-key <secret key from step 4> \
  --iss did:web:<domain> \
  --aud did:web:eurosky.social \
  --lxm com.atproto.server.createAccount \
  --duration-sec 3600
```

Prepare this command, leaving only the code blank:

```bash
curl -X POST "https://eurosky.social/xrpc/com.atproto.server.createAccount" \
  -H "Authorization: Bearer <token from above>" \
  -H "Content-Type: application/json" \
  -d '{
    "did": "did:web:<domain>",
    "handle": "<domain>",
    "password": "<new password>",
    "email": "<email>",
    "verificationCode": "<code>"
  }'
```

Get the code. Open `https://eurosky.social/gate/signup?handle=<domain>&state=x`, solve the captcha, and copy the `code` value from the address bar of the page it redirects to. The code is bound to the handle, lasts five minutes, and works once. Paste it in and run the command straight away. A JSON reply containing your DID means it worked. The account starts deactivated, by design.

If it fails:

| Message | Cause |
|---|---|
| Email already taken | Email is on another Eurosky account |
| Verification is now required | Code missing from the body |
| Token could not be verified | Code expired, reused, or made for a different handle |
| External handle did not resolve to DID | `atproto-did` file not being served |
| Missing auth to create account with did | Proof token expired or wrong audience |

## 6. Swap in the PDS's key and activate

The PDS signs the account's data, so the DID document must name the PDS's key, not the one from step 4. That key only served to prove control during sign-up.

```bash
goat account login --pds-host https://eurosky.social -u did:web:<domain> -p <password>
goat account plc recommended
```

Take the `verificationMethods.atproto` value, drop the `did:key:` prefix, and put it in `publicKeyMultibase` in `did.json`. Build and deploy the site. Then:

```bash
goat resolve did:web:<domain>
goat account activate
goat account status <domain>
```

Activation fetches `did.json` fresh and fails with "verification method does not match" until the new key is live.

## 7. Set up Sequoia

Create an app password for the account. In the Bluesky app, sign in with hosting provider `eurosky.social` and identifier `<domain>`, then under settings, privacy and security, app passwords. Store it with Sequoia:

```bash
sequoia auth
```

Give the handle `<domain>` and the app password. Sequoia finds the PDS from the handle. This login does not expire. Do not use `sequoia login`, whose browser session lapses after two weeks.

Run init from inside the site folder. Sequoia searches upward for its config, so there must be no `sequoia.json` above it:

```bash
cd sites/<name>
sequoia init
```

| Prompt | Answer |
|---|---|
| Site URL | `https://<domain>` |
| Content directory | `content` |
| Cover images directory | empty |
| Public/static directory | `static` |
| Build output directory | `public` |
| URL path prefix | empty |
| Publish the post content? | yes, unless you want only titles and links published |
| Field names | title `title`, publish date `date`, tags `tags`, draft `draft`, rest empty |
| Publication setup | Create a new publication |
| Show in Discover feed? | yes |
| Automatic Bluesky posting? | no, unless wanted |

Init writes `sequoia.json`, drops the verification file at `static/.well-known/site.standard.publication`, and creates a `.gitignore` in the site folder. Delete that `.gitignore`. The root one already covers the state file.

Add `pathTemplate` and `ignore` to the config:

```json
{
  "$schema": "https://tangled.org/stevedylan.dev/sequoia/raw/main/sequoia.schema.json",
  "siteUrl": "https://<domain>",
  "identity": "<domain>",
  "contentDir": "content",
  "publicDir": "static",
  "outputDir": "public",
  "pathTemplate": "/{slug}/",
  "publicationUri": "<value init wrote>",
  "pdsUrl": "https://eurosky.social",
  "frontmatter": { "publishDate": "date" },
  "publishContent": true,
  "ignore": ["_index.md", "**/_index.md"]
}
```

`identity` names which stored login this site uses. Once two accounts are stored, Sequoia prompts on every publish for any config that lacks it, so add it to every site's config, `hansard` included.

Check the paths, then publish:

```bash
sequoia publish --dry-run
sequoia publish
```

Every path in the dry run should look like `/<section>/<file>/`. If any start with `/posts`, the config was not applied. The first publish creates one record per post and adds an `atUri` line to each Markdown file. Commit `sequoia.json`, the verification file, and those frontmatter changes.

## 8. Deploy

From now on one command does everything:

```bash
task deploy SITE=<name>
```

It runs, in order:

1. `sequoia sync --update-frontmatter`, which relinks any regenerated post to its existing record instead of creating a duplicate.
2. `sequoia publish`, which creates or updates records for changed posts.
3. `hugo build`.
4. `sequoia inject`, which adds two `<link>` tags to each post's HTML so readers can verify page and record belong together.
5. `rsync` to the host.

Confirm it worked:

```bash
curl https://<domain>/.well-known/site.standard.publication
curl -s https://<domain>/<section>/<file>/ | grep site.standard
goat account status
```

The first prints the publication's `at://` address. The second shows two link tags. Then browse `https://pds.ls/at://<domain>` to see the records as the network does.

## Day to day

- Each deploy touches the frontmatter of new posts. Commit those changes.
- Regenerated posts are handled by the sync step. Deleted posts leave their record behind on the PDS. Sequoia never deletes records. See below.
- Every deploy needs the PDS reachable. If it is down, deploy the site alone with `task build` then `task deploy-site`.
- The app password sits in `~/.config/sequoia/credentials.json`. Treat it like the SSH key. Revoke it from the account settings if it leaks.
- To change the PDS or its key later, edit `did.json` and redeploy. The DID document is the only source of truth for the identity.

## Deleting a post

Sequoia has no delete command. Removing the Markdown file removes the page from the site but leaves the record on the PDS, where readers still see it. Delete the record with goat.

Log in once with the app password:

```bash
goat account login --pds-host https://eurosky.social -u <domain> -p <app password>
```

Find the record key. It is the last segment of the `atUri` line in the post's frontmatter, after `site.standard.document/`. Then:

```bash
goat record delete --collection site.standard.document --rkey <rkey>
```

Do it in this order, or the record comes back:

1. Delete the Markdown file from `content/`, or set `draft = true` in it to keep the text. Sequoia skips drafts.
2. Delete the record with goat.
3. `task deploy SITE=<name>` as normal.

The order matters because Sequoia never notices a deletion. Its state file still holds the record's address, and if the post's content later changes, `publish` writes to that address, which recreates the record. Once the file is gone the stale state entry is harmless.

Renamed or regenerated posts leave old records behind too. To find them, run `sequoia sync` inside `sites/<name>/` and read the "Unmatched" section, which prints the path and `at://` address of every record with no local file. Delete each with the command above. To list everything on the PDS:

```bash
goat record ls <domain> --collection site.standard.document
```

Deletion is immediate on the PDS and the relay broadcasts it, but each reader app re-indexes on its own schedule, so a deleted post can linger in a feed for a while.
