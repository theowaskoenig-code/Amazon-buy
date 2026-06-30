"""DOM selectors and locale strings for amazon.de (with English fallbacks).

Amazon changes its markup often and runs A/B variants, so every selector here is
a best-effort guess. Each helper tries several candidates. If detection or
checkout stops working, this is the first file to update.
"""

# --- Buyability controls ---------------------------------------------------
BUY_NOW_BUTTON = "#buy-now-button"
ADD_TO_CART_BUTTON = "#add-to-cart-button"

# --- Product metadata ------------------------------------------------------
PRODUCT_TITLE = "#productTitle"

# Price: '.a-offscreen' usually holds the fully-formatted price string
# (e.g. "1.199,00 €"). Fall back to the visible whole/fraction spans.
PRICE_OFFSCREEN = (
    "#corePrice_feature_div .a-price .a-offscreen, "
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen, "
    "#apex_desktop .a-price .a-offscreen, "
    ".a-price .a-offscreen"
)
PRICE_WHOLE = ".a-price .a-price-whole"

# Seller / merchant of the active buy-box offer.
SELLER_LINK = "#sellerProfileTriggerId"
MERCHANT_INFO = "#merchant-info, #tabular-buybox, #fulfillerInfoFeature_feature_div"

# Availability block.
AVAILABILITY = "#availability"

# Colour variant swatches (twister).
COLOR_SWATCHES = "#variation_color_name li, #inline-twister-row-color_name li"

# --- Checkout / place-order controls --------------------------------------
# The "Buy Now" turbo checkout renders inside an iframe in most locales.
TURBO_CHECKOUT_IFRAME = "#turbo-checkout-iframe"
PLACE_ORDER_BUTTONS = (
    "#turbo-checkout-place-order-button, "
    "#placeYourOrder, "
    "#submitOrderButtonId input, "
    "input[name='placeYourOrder1'], "
    "#bottomSubmitOrderButtonId input, "
    "#sc-buy-box-place-order-button input"
)

# --- Locale text markers ---------------------------------------------------
# Strings that indicate the item is NOT buyable (de + en).
OUT_OF_STOCK_MARKERS = (
    "derzeit nicht verfügbar",  # de
    "nicht auf lager",
    "currently unavailable",  # en
    "out of stock",
    "we don't know when or if this item will be back in stock",
)

# Strings that indicate it IS in stock (positive signal, de + en).
IN_STOCK_MARKERS = (
    "auf lager",
    "in stock",
    "nur noch",  # "Nur noch X auf Lager" (only X left)
    "only",
)

# "Sold by" prefixes used to extract the merchant name from merchant-info text.
SOLD_BY_PREFIXES = (
    "verkauf durch",  # de
    "verkauft von",
    "sold by",  # en
    "ships from and sold by",
)

# CAPTCHA / bot-check markers — when seen we pause and ask the human for help.
CAPTCHA_MARKERS = (
    "enter the characters you see below",
    "geben sie die zeichen ein",
    "/errors/validatecaptcha",
    "api-services-support@amazon",
    "zur bestätigung, dass sie kein roboter sind",
)
