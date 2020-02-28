<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:yelp="http://www.gnome.org/yelp/ns"
                xmlns="http://www.w3.org/1999/xhtml"
                extension-element-prefixes="yelp"
                version="1.0">

<xsl:template name="html.head.custom">
  <link rel="stylesheet" href="/css/bootstrap.min.css" type="text/css"/>
  <link rel="stylesheet" href="/css/eos-help-center-style.css" type="text/css"/>
  <link rel="stylesheet" href="/css/article-style.css" type="text/css"/>
</xsl:template>

<xsl:template name="l10n-endless-text">
  <xsl:param name="msgid"/>
  <xsl:call-template name="l10n.gettext">
    <xsl:with-param name="domain" select="'yelp-endless'"/>
    <xsl:with-param name="msgid" select="$msgid"/>
    <xsl:with-param name="lang" select="$l10n.locale"/>
  </xsl:call-template>
</xsl:template>

<xsl:template name="html.top.custom">
  <xsl:param name="node" select="."/>
  <nav id="sidebar">
    <h3 class="first"><a href="index.html">
      <xsl:call-template name="l10n-endless-text">
        <xsl:with-param name="msgid" select="'sidebar.link.index'"/>
      </xsl:call-template>
    </a></h3>
    <ol>
      <li><a href="shell-overview.html"><span>
        <xsl:call-template name="l10n-endless-text">
          <xsl:with-param name="msgid" select="'sidebar.link.shell-overview'"/>
        </xsl:call-template>
      </span></a></li>
      <li><a href="files.html"><span>
        <xsl:call-template name="l10n-endless-text">
          <xsl:with-param name="msgid" select="'sidebar.link.files'"/>
        </xsl:call-template>
      </span></a></li>
      <li><a href="net.html"><span>
        <xsl:call-template name="l10n-endless-text">
          <xsl:with-param name="msgid" select="'sidebar.link.net'"/>
        </xsl:call-template>
      </span></a></li>
      <li><a href="hardware.html"><span>
        <xsl:call-template name="l10n-endless-text">
          <xsl:with-param name="msgid" select="'sidebar.link.hardware'"/>
        </xsl:call-template>
      </span></a></li>
      <li><a href="security-and-privacy.html"><span>
        <xsl:call-template name="l10n-endless-text">
          <xsl:with-param name="msgid" select="'sidebar.link.security-and-privacy'"/>
        </xsl:call-template>
      </span></a></li>
      <li><a href="a11y.html"><span>
        <xsl:call-template name="l10n-endless-text">
          <xsl:with-param name="msgid" select="'sidebar.link.a11y'"/>
        </xsl:call-template>
      </span></a></li>
    </ol>
  </nav>
</xsl:template>

</xsl:stylesheet>
