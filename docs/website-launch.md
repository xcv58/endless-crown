# Endless Crown website

Production URL: https://crown.jenny.media/

## Hosting

The website is deployed on Vercel, which also manages DNS for `jenny.media`.

- Team: `xcv58s-projects`
- Project: `endless-crown`
- Repository: `xcv58/endless-crown`
- Production branch: `master`
- Root directory: `website`
- Public output: `website/dist`
- Deployment configuration: `website/vercel.json`

Vercel runs the website interaction checks before deployment. GitHub also runs them for changes under `website/`. Pull requests receive preview deployments; merging to `master` publishes production.

The static site includes the homepage, privacy page, custom 404 page, theme preferences, App Store badge, watch installation FAQs, and a user-initiated video with sound enabled by default.

## Release checks

Before publishing changes, check both themes, mobile layout, Watch installation FAQs, and video playback. After deployment, verify the homepage and `/privacy/`, App Store link, HTTPS, and the video asset at the production domain.

Before the initial launch, all six interaction checks passed, and Chromium browser checks covered desktop and mobile themes, theme persistence to the privacy page, the installation FAQ, and unmuted video playback. Decorative effect marks were contained to prevent horizontal overflow on narrow screens. These checks do not constitute physical iPhone or Apple Watch testing.

## Earlier design preview

The private Sites preview at https://endless-crown.chenyihonglove.chatgpt.site/ was used for design iteration. It is not the production host. Do not apply its previously proposed CNAME or verification TXT records to `crown.jenny.media`; the domain is served by Vercel.
