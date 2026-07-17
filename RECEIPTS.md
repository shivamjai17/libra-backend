# Receipts & Logos — setup

Payments now auto-generate a GST receipt PDF, store it, and text the student a
short link. Logos are captured at onboarding (or in Settings) and printed on
every receipt.

```
Collect payment → build PDF (ReportLab) → store in S3
                → SMS: "…Receipt: https://api.writtly.in/r/AbC123"
                → /r/{token} redirects to the PDF
```

Works with no setup in dev (files go to `./media`). Production needs the two
steps below.

---

## 1. S3 bucket for assets

Console → S3 → **Create bucket**
- Name: `writtly-assets`, Region: `ap-south-1`
- **Uncheck** "Block all public access" (receipt links are opened by students
  from their phones, so objects must be readable). Acknowledge the warning.
- Create.

Then **Permissions → Bucket policy** → paste (read-only, nothing else):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadAssets",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::writtly-assets/*"
  }]
}
```

> Receipt URLs are unguessable (random per-payment keys + random link tokens),
> so public-read means "anyone with the link", like a Google Drive share link.
> If you'd rather have expiring links, tell me and I'll switch to presigned URLs.

## 2. Let the EC2 write to the bucket

The instance currently has **no IAM role**, so it can't upload. Give it one:

1. IAM → **Roles → Create role** → Trusted entity: **AWS service** → **EC2** → Next
2. **Create policy** (new tab) → JSON:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:PutObject", "s3:GetObject"],
       "Resource": "arn:aws:s3:::writtly-assets/*"
     }]
   }
   ```
   Name it `writtly-s3-assets` → Create.
3. Back in the role wizard: attach `writtly-s3-assets` → name the role
   `writtly-ec2-role` → Create.
4. EC2 → Instances → select `writtly-api` → **Actions → Security → Modify IAM role**
   → choose `writtly-ec2-role` → Update.

No keys on the box — the SDK picks the role up automatically.

## 3. Backend env

Add to `/home/ubuntu/libradesk-backend/.env`:

```
S3_BUCKET=writtly-assets
S3_REGION=ap-south-1
PUBLIC_BASE_URL=https://api.writtly.in
```

`PUBLIC_BASE_URL` is what builds the short link, so it must be your real API
domain. Then:

```bash
cd /home/ubuntu/libradesk-backend
git pull
./venv/bin/pip install -r requirements.txt     # reportlab, boto3, pillow
sudo systemctl restart writtly-api
```

The new `payments.receipt_url` / `receipt_token` columns are added
automatically on boot — no manual migration.

## 4. Verify

```bash
# collect a payment via the app, then:
sudo journalctl -u writtly-api -n 30 --no-pager | grep -i receipt
```
Open the link from the SMS — the PDF should load.

---

## SMS / DLT note (India)

The receipt message is kept to **one 160-char segment**:

```
Hi Kavya, payment of Rs 3,000 received at StudyHub. Thank you! Receipt: https://api.writtly.in/r/90-d4G45DvQ
```

For real delivery to +91 numbers you still need **DLT registration**, and the
template you register must match this wording *including the URL placeholder*.
Carriers reject messages with unregistered links, so register
`https://api.writtly.in` as the sender's approved URL.

## What's on the receipt

A5 portrait: logo + library name/address/GSTIN · receipt no + date · student
name/ID · plan + period · payment mode · taxable value, CGST 9%, SGST 9% ·
total · "computer generated" footer. Accent colour follows the library's
`accent_color`.

GST split assumes **intra-state (CGST+SGST)**, which is right for a study
centre serving local students. If you ever need IGST for out-of-state, that's a
small change.
